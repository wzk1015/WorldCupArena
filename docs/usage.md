# WorldCupArena — Usage Guide

This is the "how do I actually run it" document. Everything else (why, what we measure, cost) is in the [README](../README.md) and [docs/cost_estimate.md](cost_estimate.md).

---

## 0. Prerequisites

- Python ≥ 3.10
- `git` (for cloning)
- API keys for at least one vendor — put them in `.env` (see [.env.example](../.env.example))
- ~5 minutes

```bash
git clone <repo-url> WorldCupArena && cd WorldCupArena
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
$EDITOR .env          # fill in at least OPENAI_API_KEY or DEEPSEEK_API_KEY
```

If you route through a 中转/proxy endpoint, set `OPENA_BASE_URL` or other base url envs in `.env` — every runner honours it.

---

## 1. The lifecycle of a fixture

Every fixture flows through these phases (automated by the scheduler):

```
ingest → populate → lock+predict → (kickoff) → live_update → truth+grade
```

| Phase | Scheduler name | Command | What it produces |
|-------|---------------|---------|-----------------|
| **ingest**   | `ingest`       | `src.ingest.api_football --fixture-id … --out fixture.json` | `data/snapshots/<id>/fixture.json` |
| **populate** | `populate`     | `src.pipeline.orchestrator populate --fixture …` | `context_pack` (squads, form, news, stats) |
| **lock**     | `lock_predict` | `src.pipeline.orchestrator lock --fixture …` | `snapshot_hash` in `fixture.json` |
| **predict**  | `lock_predict` | `src.pipeline.orchestrator predict --fixture …` | `data/predictions/<id>/<model>__<setting>.json` |
| **live update** | `live_update` | `src.pipeline.orchestrator live_update --fixture-id … --wca-id …` | real-time score/status in `data/live/<id>.json`; auto-triggers grade when finished |
| **grade**    | `truth_grade`  | `src.pipeline.orchestrator grade --fixture-dir …` | `data/results/<id>/*.json` + rebuilt leaderboard |

> `grade` needs `truth.json` next to `fixture.json`. In automated runs this is fetched automatically. For manual dry-runs, hand-edit or fetch via `src.ingest.api_football --fixture-id <ID> --out truth.json`.

---

## 2. Fastest path: run the scheduler locally

The easiest way to validate the full pipeline is to run the same scheduler the cron job uses:

```bash
# Show which phases are currently due for each fixture
python -m src.pipeline.scheduler show

# Run all due phases (idempotent — safe to run repeatedly)
python -m src.pipeline.scheduler tick

# Run a specific phase only
python -m src.pipeline.scheduler tick --phase lock_predict
python -m src.pipeline.scheduler tick --phase live_update   # fetch live score (all due fixtures)

# Or target a single fixture directly:
python -m src.pipeline.orchestrator live_update \
    --fixture-id 12345 \
    --wca-id Premier-League_Arsenal_Chelsea_2026-05-01
```

After a tick, inspect outputs:
- `data/predictions/<fixture_id>/<model>__<setting>.json` — raw model output
- `data/results/<fixture_id>/<model>__<setting>.json` — scored output (after grading)
- `data/search_logs/<fixture_id>/<model>__<setting>.json` — S2 search sources

View the results in a browser:

```bash
python3 -m src.leaderboard.build_site
python3 -m http.server --directory docs/site 8000
# open http://localhost:8000 in your browser
```

---

## 3. Testing on this weekend's real fixtures (Premier League & friends)

Scenario: you want to predict, say, **Arsenal vs Aston Villa** scheduled for Saturday 19:30 UTC.

### 3.1 Ingest the fixture snapshot (T-48h to T-24h)

```bash
# API-Football fixture ID — look it up on api-football.com/documentation
FIXTURE_ID=1234567

python -m src.ingest.api_football \
    --fixture-id $FIXTURE_ID \
    --out data/snapshots/pl_ars_avl_2026_04_18/fixture.json

python -m src.pipeline.orchestrator populate \
    --fixture data/snapshots/pl_ars_avl_2026_04_18/fixture_test.json --recent-n 10
```

The ingestor pulls squads, recent form, injury news, and bookmaker closing odds into `context_pack`. If an adapter isn't ready yet (e.g. for a minor league), hand-author the snapshot — only the `fixture_id`, `kickoff_utc`, `lock_at_utc`, `home`, `away`, and `context_pack` fields are required.

### 3.2 Lock at T-24h

```bash
python -m src.pipeline.orchestrator lock \
    --fixture data/snapshots/pl_ars_avl_2026_04_18/fixture.json
```

Writes `snapshot_hash`. Any subsequent change to the fixture file changes the hash — and we compare hashes at scoring time — so don't edit after lock.

### 3.3 Predict

```bash
python -m src.pipeline.orchestrator predict \
    --fixture data/snapshots/pl_ars_avl_2026_04_18/fixture.json \
    --parallel 8
```

Runs every (model × setting) pair configured in [configs/models.yaml](../configs/models.yaml) × [configs/settings.yaml](../configs/settings.yaml). Each prediction is schema- and semantics-validated (including win_probs ↔ score_dist consistency); malformed outputs trigger up to 2 repair retries. If a prediction file already exists but contains an error, it is automatically re-run. Per-call cost, token usage, and validation report are stored with the prediction.

S2 model search sources are also saved to `data/search_logs/<fixture_id>/` for post-run review.

### 3.4 Grade (T+3h to T+24h after kickoff)

```bash
# Pull the real result
python -m src.ingest.api_football --fixture-id $FIXTURE_ID \
    --out data/snapshots/pl_ars_avl_2026_04_18/truth.json

# Score
python -m src.pipeline.orchestrator grade \
    --fixture-dir data/snapshots/pl_ars_avl_2026_04_18

# Rebuild and view the website locally
python3 -m src.leaderboard.build_site
python3 -m http.server --directory docs/site 8001
# now open http://localhost:8000 in your browser
```

> In automated runs, grading is triggered immediately when the live score status becomes "Match Finished" (during the T+0h → T+3h `live_update` phase), without waiting for the T+3h window.

---

## 4. Running a subset of models / settings

Easiest: comment out the entries you don't want in [configs/models.yaml](../configs/models.yaml), or maintain a private copy and pass it in via:

```bash
WORLDCUPARENA_MODELS_YAML=configs/models.mine.yaml \
  python -m src.pipeline.orchestrator predict --fixture ...
```

Per-model setting coverage is declared via `settings_supported:` on each entry. In the current 2-setting regime, non-tool LLMs declare `[S1]` and tool-using models / agents declare `[S2]` — see [configs/settings.yaml](../configs/settings.yaml) for what each setting injects.

---

## 5. Cost control knobs

In order of biggest → smallest impact:

1. **Drop deep-research agents** — 80 % of per-fixture cost lives in those 5 agents. Keep only MiroThinker H1 + Perplexity DR for a ~$7 saving.
2. **Enable batch APIs** (OpenAI + Anthropic) — set `batch: true` in the model entry. 50 % discount, 24 h turnaround (fine for pre-kickoff locks).
3. **Prompt caching** — set `cache_system: true` on any provider that supports it. The system prompt is ~1.2k tokens and identical across fixtures.
4. **T5 frequency** — see [docs/cost_estimate.md §3.2](cost_estimate.md). The biggest remaining non-agent lever.

All of these are already wired up; they are just config flags.

---

## 6. What to inspect after a run

| Path                                                          | What's in it                                            |
|---------------------------------------------------------------|---------------------------------------------------------|
| `data/predictions/<fixture>/<model>__<setting>.json`          | raw model output + parsed prediction + cost + retries   |
| `data/predictions/<fixture>/<model>__<setting>.json` → `validation_errors` | non-empty means the final answer still had schema/semantic issues |
| `data/predictions/<fixture>/<model>__<setting>.json` → `leakage_audit` | any source with `published_at > lock_at_utc` flagged    |
| `data/results/<fixture>/<model>__<setting>.json` → `composite` | final 0-100 score                                       |
| `data/results/<fixture>/<model>__<setting>.json` → `layers`   | T1-T5 sub-scores                                        |
| `data/search_logs/<fixture>/<model>__<setting>.json`          | S2 search sources (URLs + titles + accessed_at)         |
| `data/live/<fixture>.json`                                    | real-time score snapshot during match (T+0h → T+3h)     |
| `data/archive/`                                               | fixtures excluded from leaderboard (moved here manually) |

---

## 7. Common problems

- **`NotImplementedError: no runner for provider X`** — add a runner under [src/runners/](../src/runners/) or remove that entry from `models.yaml`. `openai_compat` already covers OpenAI / DeepSeek / Together / DashScope / xAI / Perplexity via `base_url`.
- **`ValidationError: 'reasoning' does not contain enough characters`** — the model emitted a too-short `reasoning.overall`. The orchestrator retries twice, but if it still fails you'll see `validation_errors` populated. Usually a model-specific prompt tweak fixes it; if not, relax `minLength` in [schemas/prediction.schema.json](../schemas/prediction.schema.json).
- **`leaked_sources` non-empty** — tasks that depend on that source get 0. This is working as designed. Check whether the agent is citing a post-match recap and prompt-engineer it not to (or accept the penalty — that is the whole point of the leakage audit).
- **Clock skew issues with `lock_at_utc`** — all timestamps are UTC. Don't mix local time.

---

## Example

```bash
# 1. ingest
python -m src.ingest.api_football \
  --fixture-id 1489369 \
  --wca-id World-Cup_Group-Stage-1_Germany_Curaçao_2026-06-14 \
  --lock-at "" \
  --out data/snapshots/World-Cup_Group-Stage-1_Germany_Curaçao_2026-06-14/fixture.json

# 2. populate
python -m src.pipeline.orchestrator populate \
  --fixture data/snapshots/World-Cup_Group-Stage-1_Germany_Curaçao_2026-06-14/fixture.json

# 3. predict
python -m src.pipeline.orchestrator predict \
  --fixture data/snapshots/World-Cup_Group-Stage-1_Germany_Curaçao_2026-06-14/fixture.json \
  --parallel 8
```

## 9. Where next

- [docs/integration.md](integration.md) — "I want my model/agent on this leaderboard" (for third-party developers).
