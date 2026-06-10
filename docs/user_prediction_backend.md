# 用户预测后端接入

本文档说明 MatchMate 后端如何接入 WorldCupArena 静态页面上的当前用户预测 UI。

## 范围

源码文件：

- `docs/site/index.html`
- `docs/site/app.js`

公开测试 URL：

- `https://wzk1015.github.io/WorldCupArena/?user_predict=1`

用户预测 UI 由 URL 参数控制：

- `?user_predict=1`：显示登录按钮和用户预测 UI。
- `?user_predict=0` 或无参数：隐藏登录按钮和用户预测 UI。

前端负责的逻辑：

- 渲染尚未开始比赛的预测控件。
- 让用户先选择 `home`、`draw` 或 `away`。
- 让用户可选开启准确比分输入。
- kickoff 之后，或 实时状态 不再是 `Not Started` 时，隐藏编辑入口。
- 在已结束比赛中展示当前用户的历史预测。
- 在排行榜中本地计算当前用户的赛果准确率和可选的准确比分准确率。
- 排行榜永远不展示其他用户。

后端负责的逻辑：

- 使用 Logto 鉴权用户。
- 保存当前用户对某一场比赛的预测。
- 页面打开时返回当前用户之前保存过的预测。
- 执行服务端校验，并在开赛后锁定预测。

## 前端配置

在 `app.js` 之前注入以下全局变量，或通过 MatchMate 宿主页面暴露等价信息：

```html
<script>
window.MATCHMATE_USER_PREDICTION_CONFIG = {
  apiBase: "https://www.matchmate.tv/api/predict",
  loginUrl: "https://www.matchmate.tv/login"
};
</script>
```

如果缺少 `apiBase` 或 API 不可用，页面会退回到 `localStorage` 预览模式。

## 鉴权 / Logto 桥接

页面会按以下顺序读取当前用户和 access token：

1. `window.MATCHMATE_USER_PREDICTION_CONFIG.accessToken`
2. `window.__MATCHMATE_AUTH__`、`window.__MATCHMATE_LOGTO__` 或 `window.__LOGTO_USER__`
3. `window.MatchMateAuth.getState()`
4. 浏览器 storage key，例如 `matchmate:logto:user`、`matchmate:user`、`logto:user`，以及对应的 access-token key
5. 父窗口 message 响应

对于嵌入式页面或由宿主页面服务的场景，父页面可以响应 auth request：

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

登录按钮会跳转到 `MATCHMATE_USER_PREDICTION_CONFIG.loginUrl`。除非配置 URL 已经包含 `redirect_uri` 或 `returnTo`，前端会把当前页面追加为 `redirect_uri`。Logto 返回后，请通过上面的任一 bridge 暴露已登录用户，这样页面右上角的登录按钮就可以显示用户名。

## API 合同

前端会调用以下端点，请求带上 `credentials: "include"`，并在可用时带上 `Authorization: Bearer <accessToken>`：

```http
GET /predictions/me
PUT /predictions/me/:fixture_id
```

`GET /predictions/me` 可以返回数组，也可以返回对象：

```json
{
  "predictions": [
    {
      "fixture_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
      "wca_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
      "home": "Mexico",
      "away": "South Africa",
      "kickoff_utc": "2026-06-11T19:00:00+00:00",
      "winner": "home",
      "score": "2-1",
      "updated_at": "2026-06-10T17:58:00.000Z"
    }
  ]
}
```

`PUT /predictions/me/:fixture_id` 接收一条预测记录：

```json
{
  "fixture_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
  "wca_id": "World-Cup_Group-Stage-1_Mexico_South-Africa_2026-06-11",
  "home": "Mexico",
  "away": "South Africa",
  "kickoff_utc": "2026-06-11T19:00:00+00:00",
  "winner": "home",
  "score": "2-1",
  "updated_at": "2026-06-10T17:58:00.000Z"
}
```

前端必需字段：

- `fixture_id` 或 `wca_id`
- `winner`，取值为 `home`、`draw`、`away` 之一

可选字段：

- `score`，可以省略/为空，或为 `N-N`
- `home`、`away`、`kickoff_utc`、`updated_at`

`PUT` 后，后端应返回已保存的记录；如果暂时做不到，至少返回足够字段，让前端可以 normalize 已保存的预测。

## 建议数据库结构

```sql
create table user_match_predictions (
  id bigserial primary key,
  user_id text not null,
  fixture_id text not null,
  winner text not null check (winner in ('home', 'draw', 'away')),
  score text null,
  home text null,
  away text null,
  kickoff_utc timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, fixture_id)
);
```

保存行为应基于 `(user_id, fixture_id)` 做 upsert。

## 校验

推荐的后端校验：

- 用户必须已鉴权。
- `fixture_id` 必须匹配已知的 WorldCupArena fixture。
- 只有开赛前，且比赛未进入 live/finished 状态时，才允许预测。
- `winner` 必须是 `home`、`draw` 或 `away`。
- 如果存在 `score`，校验 `^\d{1,2}-\d{1,2}$`。
- 如果存在 `score`，可以按产品决策要求它与 `winner` 一致。

示例：

- `winner=home`，`score=2-1`：有效。
- `winner=draw`，`score=1-1`：有效。
- `winner=away`，无 `score`：有效。
- `winner=home`，`score=0-2`：根据产品决策拒绝或规范化。

## 本地兜底

在后端接入前，前端会把预览记录存到 localStorage：

- 类登录用户：`matchmate:user_predictions:v1:<user_id>`
- 访客预览：`matchmate:user_predictions:v1:local-preview`

这个兜底只用于 UI 测试。除非产品需要一次性导入，否则后端不需要迁移这些数据。

## 后端待办

- 为 predict 页面增加 Logto login/callback 流程。
- 登录后通过一个 auth bridge 暴露当前用户和 access token。
- 在 `app.js` 加载前配置 `MATCHMATE_USER_PREDICTION_CONFIG.apiBase` 和 `loginUrl`。
- 实现 `GET /predictions/me`。
- 实现带 upsert 的 `PUT /predictions/me/:fixture_id`。
- 如果 API 位于 `www.matchmate.tv` 且静态页面仍是跨域 GitHub Pages，请为 GitHub Pages origin 添加 CORS。
- 执行服务端 kickoff/live 锁定；前端锁定只负责用户体验。
- 当前阶段继续由前端聚合排行榜。后端只需要提供当前用户自己的预测。
