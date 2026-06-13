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
| **ingest**   | `ingest`       | T-7d → T-LEAD | `src.ingest.api_football --fixture-id … --out fixture.json` | raw API-Football response → `data/snapshots/<id>/fixture.json` |
| **populate** | `populate`     | T-LEAD-24h → T-LEAD | `src.pipeline.orchestrator populate --fixture …` | adds `context_pack` — squads + recent form + stats + **news headlines** |
| **lock+predict** | `lock_predict` | T-LEAD → T+0h | `orchestrator lock` then `orchestrator predict` | `snapshot_hash` in `fixture.json` + `data/predictions/<id>/<model>__<setting>.json` |
| **live update** | `live_update` | T+0h → T+3h | `src.pipeline.orchestrator live_update --fixture-id … --wca-id …` | `data/live/<id>.json` (real-time score/status); triggers `truth_grade` early if status = "Match Finished" |
| **truth+grade** | `truth_grade` | T+3h → T+48h | `src.ingest.api_football --out truth.json` + `orchestrator grade` + `leaderboard.build` + `leaderboard.build_site` | `truth.json` + `data/results/<id>/*.json` + generated site JSON |

Phases scheduled by `src.pipeline.scheduler`:

```
T-7d       ─── ingest          ─── fixture.json  (from API-Football)
T-LEAD-24h ─── populate        ─── context_pack  (squads, form, news, stats)
T-LEAD     ─── lock_predict    ─── snapshot_hash + predictions/   (LEAD = WCA_PREDICT_LEAD_H, default 48h)
T+0h  ─── live_update     ─── data/live/<id>.json  (real-time score every 10 min)
T+3h  ─── truth_grade     ─── truth.json + results/ + leaderboard + generated site JSON
```

赛中 AI 预测不是这五个自动化阶段的一部分。GitHub workflow 只抓实时比分；
如果需要比赛过程中每 5 分钟重新调用模型预测胜平负和最终比分，请使用下面的
本地守护进程。

Each phase has its own window (see `PHASES` in `src/pipeline/scheduler.py`).
At every tick, for every fixture, every phase whose window is **currently
open** runs — and each handler is idempotent, so a 10-minute cadence is
safe (repeated ticks are no-ops, missed ticks catch up).

---

## 2. The registry: `configs/fixtures.yaml`

Add a new fixture by appending one entry. The next 10-minute cron tick picks it
up automatically — no other file has to change.

```yaml
fixtures:
  - wca_id: ucl_sf1_l1_2026
    provider_id: 1540901                # API-Football numeric fixture id
    kickoff_utc: 2026-04-28T19:00:00+00:00
    enabled: true
```

`lock_at_utc` is derived as `kickoff_utc − WCA_PREDICT_LEAD_H hours` (default **48h**; set in `src/pipeline/scheduler.py`).

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
4. python -m src.leaderboard.build_site         # validate bilingual site payload
5. git commit -m "automate: tick <timestamp>"   # if any source artifact changed
   git push                                     # back to main
```

The commit step is what makes the site update visibly — once main moves, the
`pages` workflow regenerates `data.en.json`, `data.zh.json`, and default
`data.json`, then redeploys `docs/site/`.

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
| `WCA_MODEL_PROXY=gptplus5` + `GPTPLUS5_API_KEY` / `GPTPLUS5_BASE_URL` | optional GPTPlus5/New API proxy for supported `closed_llm` / `open_llm` / `search_llm` / `deep_research_agent` entries | optional |

Any provider whose key is missing is simply skipped; the scheduler does not
fail the whole tick.

---

## 6. The website deploy: `.github/workflows/pages.yml`

Trigger: push to `main` affecting site sources, leaderboard builders, fixture
config, or committed data artifacts. The `automate` workflow commits those
source artifacts, so each successful tick triggers a site redeploy.

The site itself is **static** — plain HTML + vanilla JS reading generated
`data.en.json`, `data.zh.json`, and default `data.json`. These files are
created during the Pages workflow and ignored by git to avoid recurring merge
conflicts on large generated payloads. No Node dependency.

See [docs/site/README.md](site/README.md) for site internals.

---

## 7. Local in-play AI predictions

`src.pipeline.live_predict` is a manual matchday tool. It fetches the current
API-Football fixture state, calls selected models, writes
`data/live_predictions/<wca_id>/<model>__LIVE.json`, and rebuilds the static
site payload. These records are **not** read by grading or leaderboard code,
and `data/live_predictions/` is git-ignored to avoid matchday merge conflicts.

One-off live prediction:

```bash
python -m src.pipeline.live_predict once \
  --fixture-id 1540901 \
  --wca-id ucl_sf1_l1_2026 \
  --models gpt-5.4 gemini-3.1-pro-preview-thinking
```

Run a daemon that refreshes every 5 minutes:

```bash
python -m src.pipeline.live_predict daemon \
  --fixture-id 1540901 \
  --wca-id ucl_sf1_l1_2026 \
  --models gpt-5.4 gemini-3.1-pro-preview-thinking \
  --interval-seconds 300
```

Each cycle writes the latest raw live score to `data/live/<wca_id>.json`, writes
the latest model forecast to `data/live_predictions/`, and then runs
`python -m src.leaderboard.build_site` unless `--no-build-site` is supplied.
Keep a local static server open while the daemon runs:

```bash
python -m http.server -d docs/site 8000
```

The live prediction schema is intentionally smaller than the pre-match schema:
it contains current win/draw/loss probabilities, one most likely final score,
future goalscorer candidates after the current minute, reasoning, sources,
tokens, and cost. It does not predict lineups, match statistics, cards,
substitutions, or key events.

## 8. Local testing

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

## 9. Timeline in one picture

```
     fixture added to fixtures.yaml
             │
             ▼
   ┌──────── cron every 10 minutes ────────┐
   │                                       │
T-7d  ──────── ingest           (fetch fixture.json from API-Football)
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

That's all. The 10-minute cron at .github/workflows/automate.yml now picks it up:

T-7d → ingests fixture.json

T-48h → populates context_pack (news included)

T-24h → locks + runs every model prediction

T+3h → fetches truth, grades, rebuilds leaderboard + site

View the website: https://<your-gh-username>.github.io/<repo-name>/. It auto-deploys every time the automation commits new data to main (triggered via .github/workflows/pages.yml).

Force-run without waiting for cron: Actions → automate → Run workflow.

Local preview: python -m src.leaderboard.build_site && python -m http.server -d docs/site 8000 → open http://localhost:8000.
