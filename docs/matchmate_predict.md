# MatchMate `/predict/` 集成说明

本文档记录 WorldCupArena 如何在 MatchMate 中通过 `/predict/` 提供服务。

## 整体结构

WorldCupArena 负责预测流水线和静态站点文件：

- `docs/site/index.html`
- `docs/site/app.js`
- `docs/site/data.en.json`
- `docs/site/data.zh.json`
- `docs/site/data.json`

MatchMate 不会把这些文件复制进 `frontend/dist/`，只是在 `/predict/` 下直接暴露 WorldCupArena 的 `docs/site/` 目录。

因此，不启动 MatchMate 后端、Redis、比赛注册表、实时比赛准备流程或其他 MatchMate 页面，也可以单独验证 `/predict/`。

## 本地仅页面验证

在 WorldCupArena 仓库根目录下，先生成一次被 git 忽略的站点数据：

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon --once --no-pipeline
```

然后只启动 MatchMate 前端：

```bash
cd /home/wzk/MatchMate/frontend
npm run dev -- --host 127.0.0.1
```

打开：

```text
http://127.0.0.1:5173/predict/
```

这个路径不需要 MatchMate `.env`、后端、Redis 或比赛准备流程，只需要前端 dev server 和 `WorldCupArena/docs/site/` 里的静态文件。

本地前端需要 Node `20.19+` 或 `22.12+`。MatchMate 的 `npm run dev` 脚本会使用 `frontend/scripts/run-vite.sh`，在可用时选择兼容的 Node，例如这台 VM 上的 `/usr/lib/code-server/lib/node`。如果旧的 `node_modules` 缺少 Vite/Rolldown 可选原生依赖，请在启动 dev 前执行一次：

```bash
cd /home/wzk/MatchMate/frontend
npm install
```

使用 Vite 输出的 URL。如果 `5173` 已被占用，Vite 可能会选择 `5174` 或其他邻近端口。

## WorldCupArena 持续维护

为了保持站点数据新鲜，需要把 WorldCupArena daemon 作为独立进程运行。比赛页面预期实时比赛日更新间隔为 300 秒：

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon \
  --interval-seconds 300
```

每个循环可以执行：

```bash
python -m src.pipeline.scheduler tick
python -m src.pipeline.live_predict once ...
python -m src.leaderboard.build_site
```

只有传入 `--live-predict` 时才会运行 `live_predict`。默认实时模式使用 `--only-live`，所以开赛前只刷新数据源快照并重建站点，不会调用模型。中场休息/HT 期间也会刷新数据源快照，但跳过模型调用，即使启用了 `--always-predict-live` / `--predict-every-cycle`。一旦比赛进入进行中状态，每个 300 秒循环都会为每个选定模型生成新的实时预测，并追加到该模型的实时预测历史中。

使用三个模型预测秘鲁 vs 西班牙的示例：

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon \
  --interval-seconds 300 \
  --no-pipeline \
  --live-predict \
  --live-fixture-id 19701371 \
  --live-wca-id Friendly-International_Peru_Spain_2026-06-09 \
  --live-provider sportmonks \
  --live-models gpt-5.4 gemini-3.1-pro-preview-thinking claude-opus-4-7-thinking
```

只有在明确希望 daemon 每个循环都生成新的模型预测时，才添加 `--always-predict-live`，包括开赛前也预测。正常比赛日实时预测应省略它，让 5 分钟预测节奏只在比赛开始后生效。

因此，daemon 会就地更新 `docs/site/data.en.json`、`docs/site/data.zh.json` 和 `docs/site/data.json`。这些 payload 现在是模型原生输出：站点构建器不再执行 LLM 后处理翻译，所以需要中文展示文本时，预测运行本身应直接产出中文叙述。已检出的 `index.html` 和 `app.js` 改动也会立即可见，因为 MatchMate 直接服务这个目录。

常用参数：

```bash
python3 -m src.leaderboard.site_daemon --once
python3 -m src.leaderboard.site_daemon --once --no-pipeline
python3 -m src.leaderboard.site_daemon --interval-seconds 300 --git-pull
python3 -m src.leaderboard.site_daemon --phase live_update
python3 -m src.leaderboard.site_daemon --disable-translation-llm
python3 -m src.leaderboard.site_daemon --live-predict --live-fixture-id 19701371 --live-wca-id Friendly-International_Peru_Spain_2026-06-09
python3 -m src.leaderboard.site_daemon --always-predict-live --live-predict --live-fixture-id 19701371 --live-wca-id Friendly-International_Peru_Spain_2026-06-09
python3 -m src.leaderboard.site_daemon --strict
python3 -m src.pipeline.live_predict daemon --fixture-id 19701371 --wca-id Friendly-International_Peru_Spain_2026-06-09 --provider sportmonks --interval-seconds 300 --only-live --stop-after-finished
```

运行真实流水线需要 `WorldCupArena/.env` 中的运行时密钥，例如足球数据源和模型供应商密钥。仅页面 smoke test 可以使用 `--no-pipeline`，不需要这些密钥。

## 完整赛事预测

WorldCupArena 还支持 FIFA World Cup 2026 的独立完整赛事预测页面。它刻意与 `configs/fixtures.yaml` 和 scheduler 分离：不会创建逐场比赛任务，也不会影响单场比赛排行榜。

静态赛事输入位于：

```text
configs/world_cup_2026_tournament.json
data/tournament_context/world_cup_2026/context_pack.md
```

spec 包含 12 个小组、72 场小组赛，以及 73-104 号淘汰赛模板。它由 FIFA 官方赛事页面和公开的小组赛/淘汰赛赛程页面生成。context pack 只注入给 S1/非搜索模型；S2/搜索模型会在 prompt 中被要求自行搜索最新大名单、伤病、状态和新闻。

在 WorldCupArena 仓库根目录手动运行完整赛事预测：

```bash
python3 -m src.pipeline.tournament_predict list-models
python3 -m src.pipeline.tournament_predict run --models gpt-5.4 qwen3-max
python3 -m src.pipeline.tournament_predict run --force
python3 -m src.leaderboard.build_site
```

不带 `--models` 的 `run --force` 会选择所有已配置的非 baseline 模型，因此可能很慢也很贵。建议用 `--models ...` 分批运行。预测器会为每个模型写入一条记录：

```text
data/tournament_predictions/world_cup_2026/<model_id>__<setting>.json
```

每个模型的 runner 分为两个阶段：

1. 模型预测每场小组赛的比分、赛果和进球者。
2. 代码根据这些比分计算小组积分榜，按积分、净胜球、进球数和队名兜底排序，然后确定 1/16 决赛。
3. 同一个模型收到它自己计算出的积分榜和已确定的 1/16 决赛对阵后，继续预测 73-104 号比赛，包括冠军和进球者。
4. 代码根据模型保存的比赛预测，推导冠军、亚军、季军和射手榜。

对于成绩最好的小组第三，当前实现使用 FIFA 已公布的每个 1/16 决赛席位允许的小组池，并对 8 支晋级的小组第三进行回溯匹配。如果 MatchMate 后续需要精确的 Annex C 495 组合查表，可以替换 `src.pipeline.tournament_predict` 中的 resolver，而不需要修改前端合同。

`src.leaderboard.build_site` 会把记录暴露为 `data.json.tournament_predictions`。`/predict/` 页面渲染一个独立 section：折叠卡片展示每个模型预测的冠军和旗帜；展开后展示小组赛比分/进球者、计算出的积分榜、淘汰赛路径，以及推导出的射手榜。

## 当前用户预测前端合同

详细后端交接说明：[用户预测后端接入](user_prediction_backend.md)。

`docs/site/app.js` 现在包含仅页面级 UI，让当前 MatchMate 用户预测尚未开始的比赛。该功能只在 URL 包含 `?user_predict=1` 时启用；`?user_predict=0` 或不带该参数时保持隐藏。第一版实现是前端优先：没有配置后端 API 时使用 `localStorage`，并暴露一份小型合同，便于 MatchMate 后端后续替换本地兜底逻辑。

### 鉴权桥接

页面会按以下顺序尝试发现当前 Logto/MatchMate 用户：

- `window.MATCHMATE_USER_PREDICTION_CONFIG.accessToken`
- `window.__MATCHMATE_AUTH__`、`window.__MATCHMATE_LOGTO__` 或 `window.__LOGTO_USER__`
- 存在时调用 `window.MatchMateAuth.getState()`
- 浏览器 storage key，例如 `matchmate:logto:user`、`matchmate:user`、`logto:user`，以及匹配的 access-token key
- 父窗口 message 响应，类型为 `matchmate:auth:state`、`matchmate:logto:state` 或 `logto:user`

当 `/predict/` 被嵌入或服务在 `www.matchmate.tv` 下时，宿主页面可以响应前端请求：

```js
window.addEventListener("message", event => {
  if (event.data?.type !== "matchmate:auth:request") return;
  event.source?.postMessage({
    type: "matchmate:auth:state",
    user: { id: "user_123", name: "Alice", email: "alice@example.com" },
    accessToken: "LOGTO_ACCESS_TOKEN"
  }, event.origin);
});
```

登录按钮会在提供配置时跳转到 `MATCHMATE_USER_PREDICTION_CONFIG.loginUrl`。没有配置时，MatchMate 模式使用 `/login`，独立 WorldCupArena 模式使用 `https://logto.io/`。除非配置 URL 已经包含 `redirect_uri` 或 `returnTo`，否则当前页面 URL 会作为 `redirect_uri` 添加进去。

在 `app.js` 之前注入配置的示例：

```html
<script>
window.MATCHMATE_USER_PREDICTION_CONFIG = {
  apiBase: "https://www.matchmate.tv/api/predict",
  loginUrl: "https://www.matchmate.tv/login"
};
</script>
```

### 后端 API 形状

如果配置了 `apiBase`，前端会调用以下端点，请求带上 `credentials: "include"`，并在有 token 时带上 `Authorization: Bearer <accessToken>`：

```http
GET /predictions/me
PUT /predictions/me/:fixture_id
```

`GET /predictions/me` 可以返回数组，也可以返回 `{ "predictions": [...] }`。每条预测记录建议使用以下形状：

```json
{
  "fixture_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
  "wca_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
  "home": "Mexico",
  "away": "South Africa",
  "kickoff_utc": "2026-06-11T19:00:00+00:00",
  "score": "2-1",
  "winner": "home",
  "updated_at": "2026-06-09T03:30:00.000Z"
}
```

前端只要求 `fixture_id`/`wca_id` 和 `winner`；`score` 是可选字段。其他字段会被透传，方便后端审计和展示记录时不必再次查 fixture。`winner` 必须是 `home`、`draw` 或 `away`；如果存在 `score`，它应与比分对应的赛果一致。

### 前端行为

- 尚未开始的未来比赛会展示当前用户预测表单，核心选择是胜/平/负，并可选填写准确比分。
- 已保存预测可在开赛前编辑。一旦过了 kickoff 或 实时状态 不再是 `Not Started`，表单会消失，并由 UI 锁定预测。
- 已结束比赛会展示当前用户的预测和赛果正确性；只有用户选择填写比分时，才展示准确比分正确性。
- 排行榜会追加一行当前用户，名称为 `我的预测` / `My Prediction`。它只根据已结束比赛计算当前用户的胜平负准确率，且不会展示其他用户。
- 如果 API 不可用或未配置，预测会存入 `localStorage` key `matchmate:user_predictions:v1:<user_id>` 或 `matchmate:user_predictions:v1:local-preview`。

## 生产服务

MatchMate 仓库包含 WorldCupArena daemon 的 systemd 镜像文件：

```text
/home/ubuntu/MatchMate/deploy/systemd/worldcuparena-site-stable.service
```

在生产主机上准备 WorldCupArena 的 Python 环境：

```bash
cd /home/ubuntu/MatchMate/WorldCupArena
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt python-dotenv pyyaml
```

安装并启动 daemon：

```bash
cd /home/ubuntu/MatchMate
sudo cp deploy/systemd/worldcuparena-site-stable.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now worldcuparena-site-stable.service
sudo systemctl status worldcuparena-site-stable.service --no-pager
```

服务读取：

```text
/home/ubuntu/MatchMate/WorldCupArena/.env
```

## MatchMate 服务层

对于本地开发和旧 stable `vite preview`，MatchMate 的 Vite 配置会在 `/predict/` 直接服务 WorldCupArena。

对于生产 nginx，MatchMate nginx 镜像包含静态 alias：

```text
/home/ubuntu/MatchMate/deploy/nginx/www.matchmate.tv.conf
/home/ubuntu/MatchMate/deploy/nginx/www.matchmate.tv.v2.conf
```

修改线上 nginx 文件后：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

冒烟检查：

```bash
curl -I https://www.matchmate.tv/predict/
curl -I https://www.matchmate.tv/predict/app.js
curl -I https://www.matchmate.tv/predict/data.json
curl -I https://www.matchmate.tv/predict/.git/config
```

预期结果：前三个返回 `200`，隐藏文件探测返回 `404`。

## URL 模式

当站点在 `/predict/` 下打开时，会自动启用 MatchMate 展示模式：中文 UI、MatchMate 品牌、简化控件，以及限制参考链接数量。

使用以下地址可以查看原始 WorldCupArena 展示模式：

```text
/predict/?matchmate=0
```
