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
SITE_TRANSLATION_DISABLE_LLM=1 python3 -m src.leaderboard.site_daemon --once --no-pipeline
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

To keep the site data fresh, run the WorldCupArena daemon as its own process:

```bash
cd /home/wzk/MatchMate/WorldCupArena
python3 -m src.leaderboard.site_daemon --interval-seconds 600
```

Each cycle runs:

```bash
python -m src.pipeline.scheduler tick
python -m src.leaderboard.build_site
```

So the daemon updates `docs/site/data.en.json`, `docs/site/data.zh.json`, and
`docs/site/data.json` in-place. Checked-out changes to `index.html` and
`app.js` are also visible immediately because MatchMate serves this directory
directly.

Useful options:

```bash
python3 -m src.leaderboard.site_daemon --once
python3 -m src.leaderboard.site_daemon --once --no-pipeline
python3 -m src.leaderboard.site_daemon --interval-seconds 600 --git-pull
python3 -m src.leaderboard.site_daemon --phase live_update
python3 -m src.leaderboard.site_daemon --disable-translation-llm
python3 -m src.leaderboard.site_daemon --strict
```

Running the real pipeline requires WorldCupArena runtime secrets in
`WorldCupArena/.env`, such as API-Football and model provider keys. Page-only
smoke tests can use `--no-pipeline` and do not need those secrets.

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
