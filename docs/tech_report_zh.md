# WorldCupArena 技术报告（中文版）

草稿版本：2026-05-25。本文描述当前仓库实现、实验目标与方法设计；后续英文版和正式论文版可基于本文同步扩展。

---

## 摘要

WorldCupArena 是一个用真实足球比赛评测大语言模型和搜索型/研究型 Agent 的开放基准。它关注的不是静态知识问答，而是更接近真实世界决策的问题：模型必须在比赛开始前整合阵容、伤停、近期状态、新闻、赔率和技术统计等多源信息，输出一组可校验的概率预测，并在比赛结束后接受客观评分。

足球预测适合作为这类基准，原因有三点。第一，信息具有强时效性，很多关键证据发生在模型训练截止之后。第二，任务天然是概率性的，不能只看单次猜对或猜错。第三，一场比赛会产生多层次真值：胜平负、比分、首发、进球者、换人、黄牌、控球、射门等都可以被独立评分。因此，WorldCupArena 既能评估模型的检索能力，也能评估它对不确定性的校准、跨源证据融合和结构化输出能力。

当前实现支持两类核心设定：S1 是“给足资料、不开工具”的上下文注入设定；S2 是“模型自己搜索、工具开启”的自检索设定。通过比较同一基础模型在 S1 和 S2 下的表现，项目衡量所谓 Research Uplift，即工具化自研究相对人工整理资料包带来的增益。

## 1. 目标

WorldCupArena 的主要目标是建立一个可复现、可扩展、可自动运行的预测型 LLM/Agent 基准。

它试图回答以下问题：

1. 旗舰 LLM 在拿到完整上下文后，能否做出相对稳定、校准良好的足球预测？
2. 搜索型 LLM 或深度研究 Agent 自主检索时，是否真的优于人工预先整理的上下文包？
3. 不同厂商模型在结果预测、球员层预测、事件层预测和技术统计预测上各有什么长短板？
4. 模型能否在真实时间约束下避免赛后信息泄漏，并保持结构化输出的完整性？
5. 模型预测能否接近甚至超过传统强基线，例如庄家收盘赔率或统计模型？

这个基准不追求证明“AI 能准确预测足球”。更准确地说，它用足球这个客观、实时、高维的环境，测试模型在不确定真实世界里的研究和判断能力。

## 2. 基准对象

WorldCupArena 的一个基本样本是一场已经进入赛程表、但尚未开球的正式比赛。每场比赛在赛前形成一个 fixture snapshot，包含：

- 比赛基础信息：联赛、轮次、主客队、开球时间、场地、API-Football fixture id；
- 锁存时间：`lock_at_utc`，当前策略为开球前 24 小时；
- 上下文包：阵容、近期战绩、新闻头条、技术统计等；
- 快照哈希：`snapshot_hash`，用于保证预测后 fixture 内容没有被事后篡改。

模型需要输出一个符合 `schemas/prediction.schema.json` 的 JSON 对象。该对象包含胜平负概率、比分相关参数、阵容、进球者、助攻者、事件、技术统计和解释性 `reasoning`。项目要求模型输出的是分布和概率，而不是单个确定答案，因为预测任务的核心是校准不确定性。

## 3. 任务分层

当前任务体系定义在 `configs/tasks.yaml`，分为五层：

| 层级 | 权重 | 代表任务 | 主要指标 |
|---|---:|---|---|
| T1 核心结果 | 35% | 胜平负概率、比分分布、净胜球、晋级概率 | Brier、RPS、MAE |
| T2 球员层 | 25% | 首发、阵型、进球者、助攻者、全场最佳 | Jaccard、F1、nDCG、Top-1 |
| T3 事件层 | 15% | 进球分钟、换人、黄牌、点球、乌龙 | Hungarian minute MAE、event-F1 |
| T4 战术与技术统计 | 15% | 控球、射门、射正、角球、传球成功率、犯规、扑救、防守动作 | sMAPE |
| T5 赛事宏观 | 10% | 小组排名、淘汰赛路径、冠军、金靴、奖项 | Kendall tau、bracket score、Brier、nDCG |

T1 内部强调最核心的两项预测：胜平负概率占 T1 的 55%，比分分布占 T1 的 35%。这意味着模型不能只给出“谁更强”的模糊判断，还要把这种判断落实到可评分的概率结构上。

T5 主要用于世界杯或完整赛事预测。对于单场比赛，核心评分主要来自 T1 到 T4。

## 4. 实验设定

当前只保留两个设定，定义在 `configs/settings.yaml`。

**S1：上下文注入，无工具。**  
模型收到完整 context pack，包括官方阵容、近期比赛、新闻头条和技术统计。这个设定衡量的是：当人类已经把赛前证据整理好，纯 LLM 能把这些证据转化为多层预测的能力。

**S2：工具开启，自主搜索。**  
模型只收到比赛头部信息和搜索指导。prompt 会说明应该搜索哪些证据类型，例如阵容、伤停、近期状态、新闻和数据，但不直接注入完整资料包。模型可以使用 provider 提供的 `web_search` 或 `google_search` 等工具。这个设定衡量的是：模型自己找资料、筛资料、整合资料的能力。

项目曾考虑更多设定，例如“无资料、无工具”和“有工具但无提示指导”。当前版本删除这些设定，因为它们不直接服务于核心问题：比较上下文喂给模型与模型自主研究之间的差异。

## 5. 模型矩阵

当前默认活跃模型由 `configs/models.yaml` 管理，采用“每家一个旗舰模型”的策略，避免榜单被同厂商大量近似模型淹没。

当前闭源 LLM 组：

- `gemini-3.1-pro-preview-thinking`：Google Gemini 3.1 Pro Preview，使用 native Gemini thinking；
- `claude-opus-4-7-thinking`：Anthropic Claude Opus 4.7，官方 API 下使用 thinking；
- `gpt-5.4`：OpenAI GPT-5.4，使用 reasoning。

当前搜索型 LLM 组：

- `gemini-3.1-pro-preview-thinking-search`：Gemini thinking + Google Search；
- `claude-opus-4-7-thinking-search`：Claude thinking + web_search；
- `gpt-5.4-search`：GPT-5.4 reasoning + web_search。

当前 open-weight / 中国模型组主要通过 OpenRouter 的 OpenAI-compatible
接口接入，公共 `id` 保持稳定，真实 provider model slug 写在
`configs/models.yaml` 的 `model` 字段中：

- `deepseek-r1`；
- `qwen3-max`；
- `kimi-k2`；
- `glm-4.5`；
- `doubao-seed-1.6-thinking`；
- `minimax-m2.7`；
- `llama-4-maverick`；
- `gemma-7b`。

其中配置里的 `open_weight` 字段用于区分真正 open-weight 模型和中国闭源/半闭源模型。网站默认展示时会优先从 `open_weight=true` 的模型里按 leaderboard 选择前三个。

当前新增 Deep Research Agent 组：

- `openai-o4-mini-deep-research` / 兼容 o4-mini deep research 配置：OpenAI Responses API + `web_search_preview`；
- `gemini-deep-research`：Google Interactions API 的 `deep-research-pro-preview-12-2025` agent。

历史上测试过云雾中转，但当前网页默认隐藏失败的 `yunwu-o4-mini-deep-research`
条目，主流程优先使用官方或 OpenRouter/OpenAI-compatible 路由。新模型接入时只
需要添加配置并注册 runner。绝大多数 OpenAI-compatible 接口可以复用
`OpenAICompatRunner`；需要长轮询、异步任务或特殊返回结构的 agent 则使用专用
runner。

## 6. 系统架构

WorldCupArena 的实现由几个相对独立的层组成。

| 模块 | 路径 | 职责 |
|---|---|---|
| 配置层 | `configs/` | 模型注册、实验设定、赛程、任务权重 |
| 数据层 | `data/` | snapshots、predictions、results、live、live_predictions、search logs |
| ingest | `src/ingest/` | 从 API-Football 和新闻源拉取 fixture、truth、context pack |
| prompt | `src/pipeline/prompt_build.py`, `prompts/` | 根据 setting 组装系统 prompt 和用户 prompt |
| runner | `src/runners/` | 按 provider 调用模型 API，统一返回文本、tokens、sources、tool calls |
| validate | `src/pipeline/validate.py` | JSON schema 和语义校验，失败后自动修复重试 |
| calibration | `src/pipeline/score_calibration.py` | 将模型输出的核心概率校准为比分分布和衍生字段 |
| orchestrator | `src/pipeline/orchestrator.py` | 单场比赛预测、锁存、评分、live update 的主入口 |
| live predict | `src/pipeline/live_predict.py` | 本地赛中守护进程，周期性调用模型更新实时预测 |
| scheduler | `src/pipeline/scheduler.py` | GitHub Actions cron 友好的全生命周期调度 |
| grader | `src/graders/` | 各层指标与复合分计算 |
| leaderboard | `src/leaderboard/`, `docs/site/` | 汇总结果并生成静态站点 |

系统的关键设计是“配置驱动 + provider runner 抽象”。模型列表不写死在业务逻辑里，orchestrator 只遍历 `models.yaml` 中支持某个 setting 的模型条目，然后通过 `build_runner()` 生成对应 runner。这样新增模型通常不需要改 pipeline，只需要补配置和必要的 provider adapter。

## 7. Runner 设计

所有 runner 都继承 `BaseRunner`，需要实现一个 `generate(system_prompt, messages)` 方法，并统一返回：

- `text`：模型最终回答文本；
- `thinking`：provider 可返回的思考摘要或 thinking trace；
- `input_tokens` / `output_tokens`；
- `tool_calls`；
- `sources`：搜索或 grounding 得到的来源；
- error 信息由 `BaseRunner.run()` 捕获并写入预测记录。

当前三个主要 runner：

**OpenAICompatRunner**  
用于 OpenAI 和 OpenAI-compatible endpoint。官方 OpenAI API 下，如果模型需要 reasoning 或 web_search，则走 Responses API；普通兼容端点继续使用 Chat Completions。GPT-5.4 search 路径不能强制 JSON mode，因为 OpenAI web_search 与 JSON mode 不兼容，所以该路径依赖 prompt 约束和后续 parser/validator 抽取 JSON。

**GeminiRunner**  
使用原生 `google-genai` SDK，而不是 OpenAI-compatible endpoint。这样可以直接传入 `types.ThinkingConfig(thinking_level="low")` 和 `types.Tool(google_search=types.GoogleSearch())`。Gemini search 的来源从 grounding metadata 中抽取。

**AnthropicRunner**  
使用 Anthropic Messages API。官方 API 下根据配置启用 thinking 和 `web_search_20250305`；对于代理 endpoint，则保留配置中的模型名和 base_url 覆盖能力。

**OpenAIDeepResearchRunner**  
使用 Responses API 启动后台 deep research 任务，并轮询到 `completed`。当前默认通过云雾网关调用 `o4-mini-deep-research` 和 `web_search_preview`，记录 token、搜索工具调用数和来源。Deep Research 模型成本高且耗时长，因此配置中将 `max_run_retries` 和 `max_format_retries` 设为较低值，避免格式失败时重复触发完整研究。

**GeminiDeepResearchRunner**  
使用 Google Interactions API 启动 `deep-research-pro-preview-12-2025`。该 agent 不接受 `system_instruction` 参数，因此 runner 会把系统约束合并进 input。若最终研究报告不是严格 JSON，runner 会追加一次普通 Gemini JSON 编译 pass，把研究报告转换成 schema 对象；这一步避免重新运行完整 Deep Research。

所有模型配置都支持 `api_key_env`、`base_url` 和 `base_url_env`。runner 会自动加载仓库根目录的 `.env`。如果 `.env` 中存在对应的 base url override，runner 会优先使用它，以支持中转或自托管端点。

## 8. 数据生命周期

单场 fixture 的生命周期如下：

```text
T-7d  到 T-24h   ingest       拉取 fixture.json
T-48h 到 T-24h   populate     填充 squads、recent form、news、stats
T-24h 到 T+0h    lock_predict 锁存 snapshot_hash，并运行所有 model x setting
T+0h  到 T+3h    live_update  每个 tick 拉取实时比分；完赛后可提前触发评分
T+3h  到 T+48h   truth_grade  拉取 truth.json，评分，重建 leaderboard
```

`src/pipeline/scheduler.py` 将上述阶段包装为幂等任务。GitHub Actions 可以每 10 分钟运行一次 `scheduler tick`：如果某阶段已经完成就跳过，如果错过了某个窗口也会在下一次 tick 尽量补上。

赛中 AI 预测是独立的本地工作流，不加入 GitHub Actions。比赛过程中可以运行：

```bash
python -m src.pipeline.live_predict daemon \
  --fixture-id <api-football-id> \
  --wca-id <wca-id> \
  --models gpt-5.4 gemini-3.1-pro-preview-thinking \
  --interval-seconds 300
```

该守护进程每轮先调用 API-Football 获取当前比分、比赛状态、已发生事件和实时技术
统计，再调用指定模型输出一个更小的 live prediction JSON。实时预测只包含：
胜平负概率、最可能最终比分、当前时刻之后的未来进球球员、简短推理、来源、token
和成本。它不预测首发、技术统计、红黄牌、换人或“关键事件”。结果写入：

```text
data/live_predictions/<fixture_id>/<model_id>__LIVE.json
```

`data/live_predictions/` 默认不纳入 git，也不会被 `grade_match` 或 leaderboard
读取。`build_site` 只把它挂到网页 incoming match 的 `live_predictions` 字段中展示。

预测结果写入：

```text
data/predictions/<fixture_id>/<model_id>__<setting>.json
```

搜索型模型的来源日志写入：

```text
data/search_logs/<fixture_id>/<model_id>__<setting>.json
```

评分结果写入：

```text
data/results/<fixture_id>/<model_id>__<setting>.json
```

站点 JSON 由 `src.leaderboard.build_site` 生成。它总是先写英文
`docs/site/data.en.json`，再通过缓存优先的翻译器生成中文
`docs/site/data.zh.json` 和默认 `docs/site/data.json`。这些生成文件不追踪进 git，
以减少自动化运行和本地开发之间的冲突。

网站当前是纯静态前端，运行在 `docs/site/index.html` + `docs/site/app.js`。
近期展示层做了几类改造：

- 中英双语：默认中文，非 MatchMate 模式下可切换英文；
- 深浅主题：`?theme=dark|light` 控制主题，默认深色；
- MatchMate 模式：`?matchmate=1` 时改为 “MatchMate AI比分预测” 品牌、隐藏语言按钮、简化排行榜控制、来源改名为“参考链接”并最多展示前 20 个；
- 模型名称显示：优先使用 `models.yaml` 的 `display_name`，而不是 slug；MatchMate 模式下会把 Qwen、Doubao、thinking/search 字样转换成更适合中文用户的显示；
- incoming match：电脑端展示全部模型，移动端默认只展开前三个模型；
- past match：电脑端默认展示排行榜选出的前四个模型，移动端默认只展开最近三场历史比赛，其余历史比赛先显示比分牌；
- 排行榜：默认按赛果准确率排序，可切换综合分；当前排序指标只显示对应指标，避免同时展示两套分数造成误读；
- 实时预测：只在 incoming/live 比赛卡片中展示，不进入历史评分和排行榜。

## 9. 输出格式与校验

模型回答必须是完整 JSON 对象。`reasoning` 必须出现在输出开头，并拆成多个必填分析字段：市场赔率、阵容、战术、历史交手/近期状态、球员对位、伤停可用性、冷门/平局/大胜路径、比分与赛果逻辑，以及各层评分理由。这样做是为了让模型显式说明判断依据，避免只给出一组保守数字、没有可审计推理的输出。

校验分三层：

1. JSON 解析：runner 先做 best-effort JSON 提取；
2. JSON Schema：用 `schemas/prediction.schema.json` 检查字段、类型、枚举和结构；
3. 语义校验：检查概率和、`predicted_result`、`headline_score` 与最高概率胜平负是否一致，生成的兼容比分分布是否自洽，首发是否 11 人，stats 是否完整，fixture_id/setting 是否匹配等。

如果失败，orchestrator 会把错误列表发回同一个模型，要求它返回修复后的完整 JSON，最多重试 `max_format_retries` 次。这个机制避免了赛后评分时才发现输出缺字段的情况。

对于 Deep Research 这类昂贵 agent，模型配置可以覆盖 `max_format_retries` 和 `max_run_retries`。当前 deep research 条目默认不做格式修复重跑，而是在 runner 内部尽量把研究报告转换为 JSON，避免为了修一个括号重新花数分钟和数十万 token。

## 10. 比分校准设计

当前策略是让模型拥有几类高层预测：

- `win_probs`：主胜、平、客胜概率；
- `predicted_result`：模型最终选择的胜平负结果；
- `headline_score`：模型倾向的代表性比分；
- `expected_total_goals`；
- `expected_goal_diff`。

模型不再输出每个比分的概率。`score_dist`、`most_likely_score` 和 over/under 概率只由 pipeline 为展示和历史兼容生成。`score_calibration.py` 会用独立 Poisson 网格，并结合模型给出的胜平负、总进球和代表性比分，生成一个归一化的兼容比分分布；当 `headline_score` 与最高概率赛果一致时，系统会保留它作为最终展示的 `most_likely_score`。

这样做的动机是降低模型在长 JSON 中手写几十个比分概率时的噪声，同时保留模型对比赛强弱、节奏和总进球的判断。最终保存的记录同时包含：

- `raw_prediction`：去除 pipeline 生成字段后的模型原始预测；
- `prediction`：经过比分校准后的最终评分版本；
- `score_calibration`：校准方法和参数记录。

## 11. 指标设计

WorldCupArena 使用尽量客观、可复现的指标。

概率类任务使用 Brier 或 RPS。胜平负是三分类 Brier；晋级、冠军等任务用二分类或多分类 Brier。比分分布会折叠成结果分布或使用排序概率评分，鼓励模型表达合理不确定性。

回归类任务使用 sMAPE 或 capped MAE。技术统计如控球、射门、传球成功率采用 sMAPE，因为它对不同量纲更稳健。净胜球误差设置上限，避免极端比分过度主导。

集合和排序任务使用 Jaccard、F1、nDCG 和 top-1 accuracy。首发阵容同时看球员名称和位置；进球者既看集合命中，也看高概率排序是否合理。

事件层任务使用 Hungarian matching。预测事件和真实事件之间的代价由时间误差和参与者是否一致共同决定，例如：

```text
cost(i, j) = |minute_pred - minute_true| + actor_mismatch_penalty
```

这种设计比简单的 exact match 更适合足球事件，因为模型可能猜对“谁会进球”但分钟不精确，也可能猜对比赛节奏但错过具体球员。

## 12. 防泄漏与复现

搜索型模型最大的风险是信息泄漏：模型可能检索到开球后或完赛后的报道。WorldCupArena 的策略是：

- fixture 在预测前写入 `snapshot_hash`；
- S2 运行保存 `sources` 和 `accessed_at`；
- 预测文件中记录 `leakage_audit`；
- 若来源提供 `published_at` 且晚于 `lock_at_utc`，相关任务可以被标记为泄漏并置零；
- search logs 单独归档，便于人工复核。

复现性来自三个方面：

1. 输入 fixture 和 truth 都落盘；
2. 每个模型输出、token、成本、错误和验证结果都落盘；
3. grading 在给定 prediction 和 truth 后是确定性的。

需要注意的是，商业模型可能存在静默版本漂移。项目应继续记录 provider 返回的模型版本、响应 id 和运行时间，以便在长期榜单里解释异常波动。

## 13. 当前结果快照

截至当前仓库中的 `docs/leaderboard/README.md`，主榜均分如下：

| 排名 | 模型 | Composite | N |
|---:|---|---:|---:|
| 1 | claude-opus-4-7-thinking-search | 51.16 | 8 |
| 2 | claude-opus-4-7-thinking | 50.84 | 10 |
| 3 | gpt-5.4 | 49.80 | 9 |
| 4 | gemini-3.1-pro-preview-thinking | 48.02 | 9 |
| 5 | gemini-3.1-pro-preview-thinking-search | 46.74 | 10 |
| 6 | gpt-5.4-search | 46.34 | 11 |

这些数字应被视为早期运行结果，而不是最终结论。当前样本数仍小，且不同 fixture 的难度差异较大。更有意义的结论需要在更多联赛、更多球队强弱组合和世界杯完整赛程上观察。

不过，早期结果已经能体现这个基准的价值：S2 并不必然优于 S1。搜索工具带来的更多信息可能改善判断，也可能引入噪声、格式风险、来源不一致和更长上下文带来的注意力稀释。因此 Research Uplift 本身是一个需要实证测量的问题，而不是默认成立的假设。

## 14. 成本与工程权衡

预测型 benchmark 的成本来自两个方向：模型调用成本和失败重试成本。WorldCupArena 当前通过以下方式控制成本：

- 默认只保留每家一个旗舰模型；
- 删除低信息量实验设定；
- 将比分分布交给 pipeline 校准，减少模型手写长概率表；
- 对格式修复设置上限；
- 对 Deep Research 设置模型级重试上限，并把 JSON 收尾放在 runner 内部；
- 搜索日志归档但不无限扩展上下文；
- 通过 `base_url_env` 支持代理、自托管和替代 endpoint。

详细成本估算见 `docs/cost_estimate.md`。成本报告中的长期预算会随模型价格、赛程规模和默认 roster 改变而更新。

## 15. 威胁与限制

**样本量限制。** 足球比赛单场方差很大，少量 fixture 不足以判断模型真实水平。项目应长期积累跨联赛和跨强弱对阵样本。

**热门球队偏置。** 模型对拜仁、曼城、皇马等强队拥有更多训练语料和新闻覆盖。较冷门球队可能更依赖 S2 搜索质量。

**赔率基线难以超越。** 庄家收盘赔率融合了大量市场信息，是非常强的预测基线。Above-Market 榜单应被视为高难目标。

**搜索质量不可控。** Provider 工具可能返回不同来源，且同一查询在不同时间结果不同。search logs 能帮助复核，但不能完全消除随机性。

**模型版本漂移。** 商业 API 可能更新模型而不改变模型名。长期报告需要记录更多响应元信息。

**格式遵循与能力混杂。** 模型分数可能受到 JSON 格式能力影响，而不仅是足球判断能力。校验与修复机制可以降低这个问题，但无法完全消除。

## 16. 路线图

短期：

- 稳定闭源、搜索、open-weight 和 Deep Research 四类模型的 S1/S2 路径；
- 持续补充 fixture，扩大样本数；
- 完善 search source 的 publication time 审计；
- 校准 OpenRouter、官方 API 和兼容 endpoint 下各模型的真实 model id、token 统计和价格；
- 在真实比赛中验证 `live_predict` 守护进程的稳定性、网页刷新体验和成本记录；
- 将当前中文报告同步为更新版英文技术报告。

中期：

- 接入更多深度研究 Agent，并区分“联网搜索模型”和“多步研究 agent”的真实增益；
- 引入 bookmaker closing odds 和统计模型作为正式 baseline；
- 增强 leaderboard 的分层可解释性，例如按 T1/T2/T3/T4 拆分趋势；
- 记录 provider model version、response id、tool traces。

长期：

- 跑完整 2026 世界杯赛程；
- 做赛前、赛中、赛后不同时间窗口的对比；
- 形成论文版技术报告，系统分析 Research Uplift、市场基线差距和模型类别差异。

## 17. 结论

WorldCupArena 把 LLM/Agent 评测从静态知识问答推进到真实、时序、概率、多源的预测环境。它的核心不是“猜中比分”这种一次性游戏，而是持续记录模型如何收集证据、如何表达不确定性、如何在严格格式和防泄漏约束下提交可评分判断。

当前系统已经具备从赛程 ingest、上下文填充、快照锁存、模型预测、格式修复、比分校准、赛后评分到静态榜单发布的完整闭环。后续工作的重点将从“跑通系统”转向“扩大样本、强化基线、分析结果”。
