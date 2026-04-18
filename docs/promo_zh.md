# WorldCupBench — 中文宣传文案合集

三版口径，按渠道调性撰写。所有数字口径与 [docs/cost_estimate.md](cost_estimate.md) 保持一致。发布前请替换 `<占位>` 项（项目链接、二维码、首页地址、作者 handle 等）。

---

## A. 公众号版（推文长文 · 约 1500 字）

**标题建议**（选一）：
- 用世界杯测 AI：我们给 20 个大模型和深度研究 Agent 办了一场预测大赛
- 2026 世界杯来了，GPT-5.4、Claude、Gemini 和 MiroThinker 谁更懂球？
- 第一个用真实足球赛事衡量 LLM 与 Agent 的基准：WorldCupBench

**正文**：

### 为什么做这件事

现有的 LLM 基准，大都在测静态知识、孤立推理：MMLU 背得好不好，AIME 解不解得对，HLE 懂不懂冷门学科。

但**真实世界的决策**，几乎从不是这样的：它需要你实时检索多源信息——伤停、舆论、赔率、战术——把它们融合进一个能输出概率而非"是/否"的推理过程，而且**结果会在某个确定的时间被客观揭晓**。

足球，尤其是顶级赛事，是这个问题的近乎完美的化身：
- 信息是**多源、异构、实时**的：首发新闻、ESPN 分析、Twitter 爆料、赔率移动；
- 推理是**概率性**的：没有任何理性的人会说"曼城必胜"，只会说"曼城胜率 58%"；
- 评分是**客观的**：90 分钟后所有答案揭晓，想赖都赖不掉；
- 结构是**分层丰富的**：一场比赛同时产出 1X2、比分分布、首发、进球时间、拦截数、最终冠军 …… 从一场球里能拿到上百个独立评价信号。

于是我们做了 **WorldCupBench**：一个用真实足球赛事评测 LLM 与深度研究 Agent 的开源基准。

### 怎么测

**五层任务（T1–T5）**：

| 层级 | 任务 | 主要指标 |
|---|---|---|
| T1 核心结果（35%）| 主客胜平概率、比分分布、晋级概率 | Brier、RPS |
| T2 球员层（25%）| 首发阵容、进球球员、阵型、MVP | Jaccard、F1+nDCG |
| T3 事件层（15%）| 进球分钟、换人、黄牌、点球 | Hungarian-MAE、事件 F1 |
| T4 技术统计（15%）| 控球、xG、射门、传球、防守 | sMAPE |
| T5 赛事宏观（10%）| 小组积分、淘汰赛对阵、冠军、金靴 | Kendall τ、bracket score |

最终合成一个 [0, 100] 的复合分，并同步发布三张榜单：**Main 主榜**、**Above-Market 跑赢市场榜**（对比 Pinnacle 收盘赔率）、**Research Uplift 研究增益榜**（比较 "Agent 自己搜" 与 "LLM 用我们喂的一样多的资料"）。

**四种设定（S0/S1/S2/S3）**：分别是"只有赛程头信息"、"加 23 人名单"、"完整资料包（阵容+近期状态+新闻+数据）"、"允许工具上网"。前三档给纯 LLM，第四档给搜索 LLM 和深度研究 Agent——这样我们能清晰拆分出"**多吃一点资料**带来的提升"和"**自己去找资料**带来的提升"。

### 谁参赛

首批已经配置好了一批旗舰选手（每家厂商一个最强款），兼顾闭源、开源、搜索与研究 Agent：

- **闭源 LLM**：GPT-5.4、Claude Sonnet 4.6、Gemini 3 Pro、Grok 4
- **开源 LLM**：DeepSeek R1、Qwen3-Max、Llama-4 Maverick
- **搜索 LLM**：Claude + web_search、GPT-5.4 + web_search、Gemini 3 Pro + Google Search、Perplexity Sonar Pro
- **深度研究 Agent**：OpenAI Deep Research、Gemini Deep Research、Perplexity Deep Research、Claude Research、MiroMind **MiroThinker H1**
- **传统基线**：Pinnacle 收盘赔率、FiveThirtyEight SPI/Elo、"无脑选强队 1-0"

**欢迎厂商认领**——你只需要往 `configs/models.yaml` 里加一条配置（通常 5 行 YAML），就可以出现在下次评测里。详见 [docs/integration.md](integration.md)。

### 严谨性：防泄漏 + 锁存快照 + 格式校验

我们花了可能比建模更多的力气在这三件事上：

1. **快照锁存（snapshot_hash）**：比赛开球前一小时冻结整个 fixture.json，写入 SHA-256 哈希。任何事后编辑都会使哈希对不上，评分自动失效。
2. **泄漏审计**：所有 Agent / 搜索结果必须附带 `accessed_at` + `published_at`。凡是 `published_at > lock_at_utc` 的来源，对应任务得 0 分，并在榜单上明确标注"该次运行存在泄漏"。
3. **提交时的完整格式校验**：schema 合规、概率归一（容差 1e-2）、首发恰好 11 人、8 项技术统计齐全、推理先于数字输出。不符则自动走最多 2 次修复重试。

### 时间线与成本

- **Phase 0（本周）**：拜仁 vs 皇马欧冠 1/4 决赛第二回合作为流水线 dry-run——结果已知，用来跑通全流程。
- **Phase 1（四月底 – 五月）**：欧冠半决赛 + 决赛共 5 场。
- **Phase 2（六月 – 七月）**：2026 美加墨世界杯全部 64 场。

**整个项目预计成本：约 450 美元（推荐 Tier C 配置）**——已经比最初 2,750 美元的设计降了 82%。完整 cost 拆解见 [docs/cost_estimate.md](cost_estimate.md)。

### 现在就可以跑

```bash
git clone <占位-项目地址>
cd WorldCupBench && pip install -r requirements.txt
cp .env.example .env && <填一个 API key>

bash scripts/dryrun_bayern_madrid.sh   # 拜仁皇马 dry-run，几分钱跑完
```

一键 dry-run 就能看到某个模型在 90 分钟之后的"答卷"被真实比分、真实首发、真实射门数打分是怎样的体验——有点像在给 AI 开期末考，但是考的是人类自己都未必答得好的题目。

### 一起玩

- **LLM / Agent 厂商**：我们非常欢迎你把自己的模型接上榜，接入成本在 10 分钟到 2 小时之间；赞助 API 额度可以把你的模型跑进完整榜单。详见 [docs/integration.md](integration.md)。
- **足球数据爱好者 / 博彩研究员**：我们的 grader 代码、历史赔率对照、泄漏审计结果全部开源，欢迎 PR 更好的 metric。
- **围观群众**：World Cup 决赛前我们会挂出"谁预测了冠军"的彩蛋页面，欢迎届时围观。

**项目主页**：<占位-GitHub 链接>
**实时榜单**：<占位-Pages 链接>

> 足球不会说谎，模型会——但模型能被基准揭穿。

---

## B. 朋友圈版（短文案 · 约 80 字 × 4 选一）

**候选 1（正式款）**
> 做了一个叫 WorldCupBench 的事：用 2026 世界杯 + 欧冠，真刀真枪评测 GPT-5.4 / Claude / Gemini / MiroThinker 这些 LLM 和 Deep Research Agent 谁更会预测足球。三张榜、五层任务、泄漏审计全开源。接入欢迎、赞助感激、围观热烈欢迎。<占位-项目链接>

**候选 2（感性款）**
> 拿真实的足球比赛来测 AI——因为足球不会说谎，而模型会。WorldCupBench：LLM vs. Agent，看看"自己上网查"到底比"我们喂资料"强多少。欢迎来围观，也欢迎把你的模型挂上来。<占位-项目链接>

**候选 3（戏谑款）**
> 我给 GPT、Claude、Gemini、DeepSeek、MiroThinker 办了个世界杯预测比赛，发现它们比我还懂球。预测值公开锁哈希，怕不怕？WorldCupBench 开源中：<占位-项目链接>

**候选 4（招募款）**
> 做了一个 AI 预测足球的公开基准 WorldCupBench，欢迎 LLM / Agent 厂商把自家模型挂上榜（10 分钟 YAML 配置就够），也欢迎赞助一点 API 额度助攻世界杯期间的全量评测。链接：<占位>

---

## C. 小红书版（中等长度 · 约 400 字 + 笔记式结构）

**标题**：🔥 给 20+ 个 AI 模型办了场世界杯预测大赛｜全开源

**封面关键词**（选两三个贴封面）：
`AI 搞笑冷知识` · `大模型评测` · `世界杯` · `科研日常` · `Agent`

**正文**：

家人们🐣 我最近在搞一件事—— 2026 世界杯还有不到俩月就开打了，我就想：这些动不动就卷数学奥赛、金融从业、医师执照考试的 AI，**到底会不会预测足球**？

毕竟预测足球得综合：
✅ 首发名单有没有到位
✅ 谁今天在发烧
✅ 哪个后卫刚被挂在热搜
✅ 赔率最近一小时往哪边移
…… 而且**比赛一结束马上就知道你说对没说对** 🤡

于是就做了一个叫 **WorldCupBench** 的开源基准🏟️：

🎯 **测谁**
- 闭源：GPT-5.4、Claude Sonnet 4.6、Gemini 3 Pro、Grok 4
- 开源：DeepSeek R1、Qwen3-Max、Llama-4 Maverick
- 搜索型：Claude / GPT + 联网，Perplexity Sonar
- 研究 Agent：OpenAI DR、Gemini DR、Perplexity DR、Claude Research、**MiroThinker H1**

🎯 **怎么测**
五层：胜负概率 / 首发阵容 / 进球时间 / 控球射门 / 最终冠军——总分 0-100，对标 Pinnacle 赔率。

🎯 **好玩的点**
📌 比赛开球前 1 小时锁存快照 + SHA-256 哈希，作弊不了
📌 Agent 用了"赛后新闻"会被自动识别出来并扣分（泄漏审计）
📌 三张榜：主榜 / 跑赢庄家榜 / "自己上网查"对"我们喂资料"的 Uplift 榜

🎯 **立刻能玩**
一行命令跑完拜仁 vs 皇马的 dry-run（几分钱）：
```
bash scripts/dryrun_bayern_madrid.sh
```

🎯 **欢迎加入**
- LLM / Agent 开发者：加一条 YAML 就能挂上榜（真的）
- 博彩 / 足球数据玩家：一起来 PR 更好的指标
- 吃瓜群众：世界杯决赛前有"谁预测了冠军"彩蛋页

⚡️ 整个项目跑完预计 **~$450**，比初版省了 82%。成本控制细节也全开源。

GitHub 在主页置顶🔗｜接入文档见 `docs/integration.md`

#人工智能 #AI大模型 #世界杯2026 #开源项目 #科研 #agent #LLM #DeepResearch #足球 #MiroMind

---

## 发布清单（checklist）

- [ ] 替换所有 `<占位>` 为真实链接
- [ ] 公众号版配首图（logo + "WorldCupBench × 2026 WC" 字样，生成 prompt 见 [docs/logo_prompt.md](logo_prompt.md)）
- [ ] 朋友圈版选 1 条，配 1 张 logo 图或榜单截图
- [ ] 小红书版封面生成：navy 背景 + 白色描边足球 + 绿色胜率柱，使用与 logo 一致的品牌色
- [ ] 首发同步：公众号 → 朋友圈 → 小红书 → X/Twitter（英文版另起）
- [ ] 项目主页 README 顶部添加"如在微信/小红书看到此项目，欢迎 star"提示
