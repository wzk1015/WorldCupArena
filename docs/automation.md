# WorldCupArena — Automation

End-to-end automation for benchmark runs: add a fixture to a YAML file, and
GitHub Actions handles every pre-match and post-match step — ingest, populate,
lock, predict, truth fetch, grade, leaderboard rebuild, and site deploy.

This document is the authoritative reference for the workflow system. See
[docs/usage.md](usage.md) for the *manual* equivalents of each command.

---

## 1. The five-phase fixture lifecycle

Every fixture flows through five pipeline phases. All times are relative to
**kickoff** (UTC).

| Phase | Scheduler name | Window | Command | What it writes |
|-------|---------------|--------|---------|----------------|
| **ingest**   | `ingest`       | T-72h → T-24h | `src.ingest.api_football --fixture-id … --out fixture.json` | raw API-Football response → `data/snapshots/<id>/fixture.json` |
| **populate** | `populate`     | T-48h → T-24h | `src.pipeline.orchestrator populate --fixture …` | adds `context_pack` — squads + recent form + stats + **news headlines** |
| **lock+predict** | `lock_predict` | T-24h → T+0h | `orchestrator lock` then `orchestrator predict` | `snapshot_hash` in `fixture.json` + `data/predictions/<id>/<model>__<setting>.json` |
| **live update** | `live_update` | T+0h → T+3h | `src.pipeline.orchestrator live_update --fixture-id … --wca-id …` | `data/live/<id>.json` (real-time score/status); triggers `truth_grade` early if status = "Match Finished" |
| **truth+grade** | `truth_grade` | T+3h → T+48h | `src.ingest.api_football --out truth.json` + `orchestrator grade` + `leaderboard.build` + `leaderboard.build_site` | `truth.json` + `data/results/<id>/*.json` + `docs/site/data.json` |

Phases scheduled by `src.pipeline.scheduler`:

```
T-72h ─── ingest          ─── fixture.json  (from API-Football)
T-48h ─── populate        ─── context_pack  (squads, form, news, stats)
T-24h ─── lock_predict    ─── snapshot_hash + predictions/
T+0h  ─── live_update     ─── data/live/<id>.json  (real-time score every 10 min)
T+3h  ─── truth_grade     ─── truth.json + results/ + leaderboard + site/data.json
```

Each phase has its own window (see `PHASES` in `src/pipeline/scheduler.py`).
At every tick, for every fixture, every phase whose window is **currently
open** runs — and each handler is idempotent, so a 10-minute cadence is
safe (repeated ticks are no-ops, missed ticks catch up).

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

`lock_at_utc` is always derived as `kickoff_utc − 24 hours`.

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
   - `ingest`: skips the API-Football download if `fixture.json` exists.
   - `populate`: skips if `context_pack.squads` is already populated.
   - `lock_predict`: skips `lock` if `snapshot_hash` is set; skips `predict`
     if `data/predictions/<wca_id>/*.json` is non-empty.
   - `live_update`: always overwrites `data/live/<wca_id>.json` with the
     latest score; if status becomes "Match Finished", immediately triggers
     `truth_grade` without waiting for the T+3h window.
   - `truth_grade`: skips the truth download if `truth.json` exists. Grade
     itself is always safe to rerun.
2. **Catch-up friendly.** Phase windows are ranges, not exact times, so a
   missed tick (workflow outage, rate-limit) just catches up on the next
   tick.
3. **Fail-isolated.** One fixture's failure doesn't stop the others — errors
   are logged and the loop continues.
4. **Multi-phase per tick.** A single tick runs every phase whose window is
   open for each fixture, so adding a new fixture whose kickoff is imminent
   can complete `ingest`, `populate`, and `lock_predict` back-to-back in one
   invocation.

---

## 4. The workflow: `.github/workflows/automate.yml`

Trigger: **`cron: "*/10 * * * *"`** — every 10 minutes, UTC.
Also accepts manual `workflow_dispatch` with an optional phase filter
(`ingest` / `populate` / `lock_predict` / `live_update` / `truth_grade`).

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
by the next 10-minute tick; the queued tick just runs when the current one
finishes.

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
   ┌──────── cron every 10 minutes ────────┐
   │                                       │
T-72h ──────── ingest           (fetch fixture.json from API-Football)
   │                                       │
T-48h ──────── populate         (squads + form + news + stats)
   │                                       │
T-24h ──────── lock + predict   (freeze snapshot, run all models)
   │                                       │
kickoff ──────── live_update    (real-time score every 10 min → data/live/)
   │                            (triggers truth_grade immediately on "Match Finished")
T+3h  ──────── truth + grade    (pull result, score, rebuild site)
             │
             ▼
      docs/site deploys to GH Pages
```


## Simplest run + deploy + view instructions

```
gh auth login
gh secret set -f .env
```

Run the automation (one-time setup):

In GitHub: Settings → Pages → Source = GitHub Actions (enables Pages).

In GitHub: Settings → Secrets and variables → Actions — add API_FOOTBALL_KEY + at least one model key (e.g. OPENAI_API_KEY).
Push. Done.

Add a fixture: append one entry to configs/fixtures.yaml and push:

```
- wca_id: pl_ars_avl_2026_04_26
  provider_id: 1234567
  kickoff_utc: 2026-04-26T19:30:00+00:00
  enabled: true
```

That's all. The hourly cron at .github/workflows/automate.yml now picks it up:

T-48h → ingests + populates context_pack (news included)

T-24h → locks + runs every model prediction

T+3h → fetches truth, grades, rebuilds leaderboard + site

View the website: https://<your-gh-username>.github.io/<repo-name>/. It auto-deploys every time the automation commits new data to main (triggered via .github/workflows/pages.yml).

Force-run without waiting for cron: Actions → automate → Run workflow.

Local preview: python -m src.leaderboard.build_site && python -m http.server -d docs/site 8000 → open http://localhost:8000.