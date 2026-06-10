# MatchMate `/predict/` integration

This document records how WorldCupArena is served inside MatchMate at
`/predict/`.

## Shape

WorldCupArena owns the prediction pipeline and the static site files:

- `docs/site/index.html`
- `docs/site/app.js`
- `docs/site/data.en.json`
- `docs/site/data.zh.json`
- `docs/site/data.json`

MatchMate does not copy these files into `frontend/dist/`. It only exposes the
WorldCupArena `docs/site/` directory at `/predict/`.

That means `/predict/` can be validated without starting the MatchMate backend,
Redis, match registry, live fixture preparation, or any other MatchMate page.

## Local Page-Only Verification

From the WorldCupArena repo root, generate the ignored site payload once:

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon --once --no-pipeline
```

Then run only the MatchMate frontend:

```bash
cd /home/wzk/MatchMate/frontend
npm run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173/predict/
```

This path does not require MatchMate `.env`, backend, Redis, or fixture setup.
It only needs the frontend dev server and the static files in
`WorldCupArena/docs/site/`.

The local frontend requires Node `20.19+` or `22.12+`. MatchMate's
`npm run dev` script uses `frontend/scripts/run-vite.sh` to choose a compatible
Node when one is available, such as `/usr/lib/code-server/lib/node` on this VM.
If an old `node_modules` install is missing Vite/Rolldown optional native
bindings, run this once before starting dev:

```bash
cd /home/wzk/MatchMate/frontend
npm install
```

Use the URL printed by Vite. If `5173` is already occupied, Vite may choose
`5174` or another nearby port.

## Continuous WorldCupArena Maintenance

To keep the site data fresh, run the WorldCupArena daemon as its own process.
The match page expects a 300 second cadence for live matchday updates:

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon \
  --interval-seconds 300
```

Each cycle can run:

```bash
python -m src.pipeline.scheduler tick
python -m src.pipeline.live_predict once ...
python -m src.leaderboard.build_site
```

`live_predict` only runs when `--live-predict` is passed. The default live mode
uses `--only-live`, so before kickoff it refreshes the provider snapshot and
rebuilds the site, but skips model calls. During halftime/HT it also refreshes
the provider snapshot but skips model calls, even if `--always-predict-live` /
`--predict-every-cycle` is enabled. Once the fixture is in play, each 300 second
cycle generates a fresh live prediction for each selected model and appends it to
that model's live prediction history.

Example for the Peru vs Spain fixture using three models:

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

Add `--always-predict-live` only when you deliberately want a fresh model
prediction on every daemon cycle, even before kickoff. For normal matchday live
prediction, omit it so the 5 minute prediction cadence starts only after the
match has begun.

So the daemon updates `docs/site/data.en.json`, `docs/site/data.zh.json`, and
`docs/site/data.json` in-place. These payloads are now model-native: the site
builder no longer performs LLM post-processing translation, so prediction runs
should produce Chinese narrative text directly when Chinese display text is
needed. Checked-out changes to `index.html` and `app.js` are also visible
immediately because MatchMate serves this directory directly.

Useful options:

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

Running the real pipeline requires WorldCupArena runtime secrets in
`WorldCupArena/.env`, such as football provider and model provider keys.
Page-only smoke tests can use `--no-pipeline` and do not need those secrets.

## Full Tournament Prediction

WorldCupArena also supports a standalone full-tournament prediction surface for
FIFA World Cup 2026. This is deliberately separate from `configs/fixtures.yaml`
and the scheduler: it does not create per-match fixture jobs and does not affect
the single-match leaderboard.

Static tournament inputs live here:

```text
configs/world_cup_2026_tournament.json
data/tournament_context/world_cup_2026/context_pack.md
```

The spec contains all 12 groups, 72 group-stage matches, and the 73-104
knockout template. It was generated from the official FIFA tournament page plus
public group/knockout schedule pages. The context pack is injected only for
S1/non-search models; S2/search models are prompted to search for current squads,
injuries, form, and news themselves.

Run the tournament predictor manually from the WorldCupArena repo root:

```bash
python3 -m src.pipeline.tournament_predict list-models
python3 -m src.pipeline.tournament_predict run --models gpt-5.4 qwen3-max
python3 -m src.pipeline.tournament_predict run --force
python3 -m src.leaderboard.build_site
```

`run --force` without `--models` selects every configured non-baseline model, so
it can be slow and expensive. Use `--models ...` for staged runs. The predictor
writes one record per model to:

```text
data/tournament_predictions/world_cup_2026/<model_id>__<setting>.json
```

The runner is two-stage per model:

1. The model predicts every group-stage match with score, result, and goalscorers.
2. Code computes group tables from those scores, ranks teams by points, goal
   difference, goals for, and name fallback, then resolves the Round of 32.
3. The same model receives its computed group tables plus the resolved Round of
   32 bracket and predicts matches 73-104, including champion and goalscorers.
4. Code derives the champion, runner-up, third place, and top-scorer table from
   the model's saved match predictions.

For best-third teams, the current implementation uses FIFA's published allowed
group pools for each Round-of-32 slot and backtracks over the eight qualified
third-placed teams. If MatchMate later needs the exact Annex C 495-combination
lookup, replace that resolver in `src.pipeline.tournament_predict` without
changing the frontend contract.

`src.leaderboard.build_site` exposes the records as
`data.json.tournament_predictions`. The `/predict/` page renders a standalone
section: collapsed cards show each model's predicted champion and flag; the
expanded path shows group match scores/scorers, computed standings, knockout
match path, and the derived scorer table.

## Current-User Predictions Frontend Contract

`docs/site/app.js` now includes page-only UI for the current MatchMate user to
predict not-started fixtures. The first implementation is frontend-only: it uses
`localStorage` when no backend API is configured, and it exposes a small contract
for the MatchMate backend to replace the local fallback later.

### Auth bridge

The page tries to discover the current Logto/MatchMate user in this order:

- `window.MATCHMATE_USER_PREDICTION_CONFIG.accessToken`
- `window.__MATCHMATE_AUTH__`, `window.__MATCHMATE_LOGTO__`, or
  `window.__LOGTO_USER__`
- `window.MatchMateAuth.getState()` when present
- browser storage keys such as `matchmate:logto:user`, `matchmate:user`,
  `logto:user`, and matching access-token keys
- a parent-window message response with type `matchmate:auth:state`,
  `matchmate:logto:state`, or `logto:user`

When `/predict/` is embedded in or served by `www.matchmate.tv`, the host page
can answer the frontend request:

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

The login button redirects to `MATCHMATE_USER_PREDICTION_CONFIG.loginUrl` when
provided. Without config it uses `/login` in MatchMate mode and
`https://logto.io/` in standalone WorldCupArena mode. The current page URL is
added as `redirect_uri` unless the configured URL already has `redirect_uri` or
`returnTo`.

Example config to inject before `app.js`:

```html
<script>
window.MATCHMATE_USER_PREDICTION_CONFIG = {
  apiBase: "https://www.matchmate.tv/api/predict",
  loginUrl: "https://www.matchmate.tv/login"
};
</script>
```

### Backend API shape

If `apiBase` is configured, the frontend calls these endpoints with
`credentials: "include"` and `Authorization: Bearer <accessToken>` when a token
is available:

```http
GET /predictions/me
PUT /predictions/me/:fixture_id
```

`GET /predictions/me` may return either an array or `{ "predictions": [...] }`.
Each prediction record should use this shape:

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

Only `fixture_id`/`wca_id`, `score`, and `winner` are required by the frontend;
the other fields are carried so the backend can audit and display records
without another fixture lookup. `winner` must be one of `home`, `draw`, or
`away`, and should match the `score` outcome.

### Frontend behavior

- Not-started incoming fixtures show a current-user prediction form with
  win/draw/loss and exact score only.
- Saved predictions can be edited until kickoff. Once kickoff passes or live
  status is no longer `Not Started`, the form disappears and the prediction is
  locked by the UI.
- Finished fixtures show the current user's prediction, result correctness, and
  exact-score correctness.
- The leaderboard appends one current-user row named `我的预测` / `My Prediction`.
  It computes only the current user's winner accuracy from finished fixtures and
  never displays other users.
- If the API is unavailable or not configured, predictions are stored under
  `localStorage` key `matchmate:user_predictions:v1:<user_id>` or
  `matchmate:user_predictions:v1:local-preview`.

## Production Service

The MatchMate repo contains a systemd mirror for the WorldCupArena daemon:

```text
/home/ubuntu/MatchMate/deploy/systemd/worldcuparena-site-stable.service
```

Prepare WorldCupArena's Python environment on the production host:

```bash
cd /home/ubuntu/MatchMate/WorldCupArena
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt python-dotenv pyyaml
```

Install and start the daemon:

```bash
cd /home/ubuntu/MatchMate
sudo cp deploy/systemd/worldcuparena-site-stable.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now worldcuparena-site-stable.service
sudo systemctl status worldcuparena-site-stable.service --no-pager
```

The service reads:

```text
/home/ubuntu/MatchMate/WorldCupArena/.env
```

## MatchMate Serving Layer

For local dev and old stable `vite preview`, MatchMate's Vite config serves
WorldCupArena directly at `/predict/`.

For production nginx, the MatchMate nginx mirror has a static alias:

```text
/home/ubuntu/MatchMate/deploy/nginx/www.matchmate.tv.conf
/home/ubuntu/MatchMate/deploy/nginx/www.matchmate.tv.v2.conf
```

After changing the live nginx file:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Smoke checks:

```bash
curl -I https://www.matchmate.tv/predict/
curl -I https://www.matchmate.tv/predict/app.js
curl -I https://www.matchmate.tv/predict/data.json
curl -I https://www.matchmate.tv/predict/.git/config
```

Expected result: the first three return `200`, and the hidden-file probe returns
`404`.

## URL Modes

When the site is opened under `/predict/`, it automatically enables MatchMate
presentation mode: Chinese UI, MatchMate branding, simplified controls, and
capped source links.

Use this to inspect the original WorldCupArena presentation:

```text
/predict/?matchmate=0
```
