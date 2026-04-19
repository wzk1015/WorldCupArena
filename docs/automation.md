# WorldCupArena — Automation

End-to-end automation for benchmark runs: add a fixture to a YAML file, and
GitHub Actions handles every pre-match and post-match step — ingest, populate,
lock, predict, truth fetch, grade, leaderboard rebuild, and site deploy.

This document is the authoritative reference for the workflow system. See
[docs/usage.md](usage.md) for the *manual* equivalents of each command.

---

## 1. The six-phase fixture lifecycle

Every fixture flows through six pipeline phases, grouped into three cron
windows. All times are relative to **kickoff** (UTC).

| Phase | Window | Command | What it writes |
|-------|--------|---------|----------------|
| **ingest**   | T-48h → T-1h | `src.ingest.api_football --fixture-id … --out fixture.json` | raw API-Football response → `data/snapshots/<id>/fixture.json` |
| **populate** | T-48h → T-1h | `src.pipeline.orchestrator populate --fixture …` | adds `context_pack` — squads + recent form + stats + **news headlines** |
| **lock**     | T-1h         | `src.pipeline.orchestrator lock --fixture …` | `snapshot_hash` written into `fixture.json` |
| **predict**  | T-1h → T+0h  | `src.pipeline.orchestrator predict --fixture …` | `data/predictions/<id>/<model>__<setting>.json` |
| **truth**    | T+3h → T+48h | `src.ingest.api_football --fixture-id … --out truth.json` | raw post-match response → `data/snapshots/<id>/truth.json` |
| **grade**    | T+3h → T+48h | `src.pipeline.orchestrator grade --fixture-dir …` + `src.leaderboard.build` + `src.leaderboard.build_site` | `data/results/<id>/*.json` + `docs/leaderboard/raw.json` + `docs/site/data.json` |

Phases are grouped by the scheduler into three cron-triggered work units:

```
T-48h ─┬─ ingest_populate ───── fixture.json + context_pack
       │
T-1h  ─┴─ lock_predict    ───── snapshot_hash + predictions/
       │
T+3h  ─── truth_grade     ───── truth.json + results/ + leaderboard + site/data.json
```

---

## 2. The registry: `configs/fixtures.yaml`

Add a new fixture by appending one entry. The next hourly cron tick picks it
up automatically — no other file has to change.

```yaml
fixtures:
  - wca_id: ucl_sf1_l1_2026
    provider_id: 1540901                # API-Football numeric fixture id
    kickoff_utc: 2026-04-28T19:00:00+00:00
    enabled: true
```

`lock_at_utc` is always derived as `kickoff_utc − 1 hour`.

Status check (dry-run; prints each fixture and the phase that would run now):

```bash
python -m src.pipeline.scheduler show
```

---

## 3. The scheduler (`src.pipeline.scheduler`)

The scheduler is the single entry-point invoked by cron:

```bash
python -m src.pipeline.scheduler tick              # run every due phase
python -m src.pipeline.scheduler tick --phase predict  # only one phase
```

Key design properties:

1. **Idempotent.** Running it twice is safe. Every phase checks "has this
   artifact already been produced?" before acting:
   - `ingest_populate`: skips the download if `fixture.json` exists.
   - `lock_predict`: skips `lock` if `snapshot_hash` is present, skips
     `predict` if `data/predictions/<wca_id>/*.json` is non-empty.
   - `truth_grade`: skips the truth download if `truth.json` exists.
2. **Catch-up friendly.** Phase windows are ranges, not exact times, so a
   missed hourly tick (workflow outage, rate-limit) just catches up on the
   next tick.
3. **Fail-isolated.** One fixture's failure doesn't stop the others — errors
   are logged and the loop continues.

---

## 4. The workflow: `.github/workflows/automate.yml`

Trigger: **`cron: "0 * * * *"`** — every hour on the hour, UTC.
Also accepts manual `workflow_dispatch` with an optional phase filter.

Job outline:

```yaml
1. checkout + python setup + pip install
2. python -m src.pipeline.scheduler show        # diagnostics
3. python -m src.pipeline.scheduler tick        # runs every due phase
4. python -m src.leaderboard.build_site || true # refresh docs/site/data.json
5. git commit -m "automate: tick <timestamp>"   # if any artifact changed
   git push                                     # back to main
```

The commit step is what makes the site update visibly — once main moves, the
`pages` workflow redeploys `docs/site/`.

Concurrency: one `automate` job at a time (`concurrency: group: automate,
cancel-in-progress: false`) — long-running predict phases never get cancelled
by the next hourly tick.

---

## 5. Required GitHub Actions secrets

| Secret | Used by | Required? |
|---|---|---|
| `API_FOOTBALL_KEY`   | ingest, truth | **yes** |
| `NEWSAPI_KEY`        | news ingest   | optional (falls back to Google News RSS if absent) |
| `GNEWS_API_KEY`      | news ingest   | optional (same fallback) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `XAI_API_KEY` | predict | at least one per provider in `models.yaml` |
| `DEEPSEEK_API_KEY` / `TOGETHER_API_KEY` / `DASHSCOPE_API_KEY` | open-LLM predict | as above |
| `PERPLEXITY_API_KEY` / `MIROMIND_API_KEY` | search-LLM / deep-research predict | as above |

Any provider whose key is missing is simply skipped; the scheduler does not
fail the whole tick.

---

## 6. The website deploy: `.github/workflows/pages.yml`

Trigger: push to `main` affecting `docs/site/**` or `docs/leaderboard/**`.
The `automate` workflow commits both directories, so each successful tick
triggers a site redeploy.

The site itself is **static** — plain HTML + vanilla JS reading
`docs/site/data.json`, which `src.leaderboard.build_site` regenerates on
every tick. No build step, no Node dependency.

See [docs/site/README.md](site/README.md) for site internals.

---

## 7. Local testing

Simulate one cron tick end-to-end against a real fixture:

```bash
# Populate the registry with a fixture whose kickoff is a few hours away.
$EDITOR configs/fixtures.yaml

# Dry-run the schedule decision:
python -m src.pipeline.scheduler show

# Actually execute the due phase (requires .env with the relevant keys):
python -m src.pipeline.scheduler tick
```

---

## 8. Timeline in one picture

```
     fixture added to fixtures.yaml
             │
             ▼
   ┌──────── cron every hour ────────┐
   │                                 │
T-48h ──────────── ingest + populate  (pulls squads, form, stats + news)
   │                                 │
T-1h  ──────────── lock + predict     (freezes snapshot, runs all models)
   │                                 │
kickoff ──────────── (real match)
   │                                 │
T+3h  ──────────── truth + grade      (pulls result, scores, rebuilds site)
             │
             ▼
      docs/site deploys to GH Pages
```


## Note

```
gh auth login
gh secret set -f .env
```