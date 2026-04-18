# WorldCupBench — Usage Guide

This is the "how do I actually run it" document. Everything else (why, what we measure, cost) is in the [README](../README.md) and [docs/cost_estimate.md](cost_estimate.md).

---

## 0. Prerequisites

- Python ≥ 3.10
- `git` (for cloning)
- API keys for at least one vendor — put them in `.env` (see [.env.example](../.env.example))
- ~5 minutes

```bash
git clone <repo-url> WorldCupBench && cd WorldCupBench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
$EDITOR .env          # fill in at least OPENAI_API_KEY or DEEPSEEK_API_KEY
```

If you route through a 中转/proxy endpoint, set `base_url` on the relevant entry in [configs/models.yaml](../configs/models.yaml) — every runner honours it.

---

## 1. The 4-step lifecycle of a fixture

Every fixture goes through exactly these four steps:

```
lock  →  predict  →  (kickoff + real match happens)  →  grade  →  leaderboard
```

Step-by-step:

| Step          | Command                                                                       | What it produces                                    |
|---------------|-------------------------------------------------------------------------------|-----------------------------------------------------|
| **lock**      | `python -m src.pipeline.orchestrator lock --fixture <fixture.json>`           | `snapshot_hash` written into `fixture.json`         |
| **predict**   | `python -m src.pipeline.orchestrator predict --fixture <fixture.json>`        | one JSON per (model, setting) in `data/predictions/<id>/` |
| **grade**     | `python -m src.pipeline.orchestrator grade --fixture-dir <snapshot_dir>`      | scored JSON in `data/results/<id>/`                 |
| **leaderboard** | `python -m src.pipeline.orchestrator leaderboard`                            | `docs/leaderboard/raw.json` (source for the static site) |

> `grade` needs `truth.json` next to `fixture.json` in the snapshot directory. Fetch it automatically via `src.ingest.api_football --fixture-id <ID> --truth` or hand-edit for dry-runs.

---

## 2. Fastest path: run the bundled dry-run

Validates the entire pipeline end-to-end on a real fixture whose truth is already known (so leakage doesn't matter):

```bash
# cheap: only hits DeepSeek-R1 (~$0.05)
bash scripts/dryrun_bayern_madrid.sh

# full flagship roster (~$10 — uses the 4 closed + 3 open + 4 search + 5 agents)
DRYRUN_MODELS=all bash scripts/dryrun_bayern_madrid.sh

# pick a subset
DRYRUN_MODELS=gpt-5.4,claude-sonnet-4-6,mirothinker-h1 bash scripts/dryrun_bayern_madrid.sh
```

The script: locks → predicts → grades → rebuilds leaderboard. Look at `data/predictions/bayern_madrid_ucl_qf_l2/*.json` to see what the models produced, and `data/results/bayern_madrid_ucl_qf_l2/*.json` for scored outputs.

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
```

The ingestor pulls squads, recent form, injury news, and bookmaker closing odds into `context_pack`. If an adapter isn't ready yet (e.g. for a minor league), hand-author the snapshot using [data/snapshots/bayern_madrid_ucl_qf_l2/fixture.json](../data/snapshots/bayern_madrid_ucl_qf_l2/fixture.json) as a template — only the `fixture_id`, `kickoff_utc`, `lock_at_utc`, `home`, `away`, and `context_pack` fields are required.

### 3.2 Lock at T-1h

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

Runs every (model × setting) pair configured in [configs/models.yaml](../configs/models.yaml) × [configs/settings.yaml](../configs/settings.yaml). Each prediction is schema- and semantics-validated; malformed outputs trigger up to 2 repair retries. Per-call cost, token usage, and validation report are stored with the prediction.

### 3.4 Grade (T+3h to T+24h after kickoff)

```bash
# Pull the real result
python -m src.ingest.api_football --fixture-id $FIXTURE_ID --truth \
    --out data/snapshots/pl_ars_avl_2026_04_18/truth.json

# Score
python -m src.pipeline.orchestrator grade \
    --fixture-dir data/snapshots/pl_ars_avl_2026_04_18

python -m src.pipeline.orchestrator leaderboard
```

---

## 4. Running a subset of models / settings

Easiest: comment out the entries you don't want in [configs/models.yaml](../configs/models.yaml), or maintain a private copy and pass it in via:

```bash
WORLDCUPBENCH_MODELS_YAML=configs/models.mine.yaml \
  python -m src.pipeline.orchestrator predict --fixture ...
```

Per-model setting coverage is declared via `settings_supported: [S0, S1, S2]` on each entry — remove settings you don't want that model to run.

---

## 5. Cost control knobs

In order of biggest → smallest impact:

1. **Drop deep-research agents** — 80 % of per-fixture cost lives in those 5 agents. Keep only MiroThinker H1 + Perplexity DR for a ~$7 saving.
2. **Enable batch APIs** (OpenAI + Anthropic) — set `batch: true` in the model entry. 50 % discount, 24 h turnaround (fine for pre-kickoff locks).
3. **Prompt caching** — set `cache_system: true` on any provider that supports it. The system prompt is ~1.2k tokens and identical across fixtures.
4. **Fewer settings** — you can drop S1 (keep S0 + S2) to halve the LLM spend with minimal signal loss.
5. **T5 frequency** — see [docs/cost_estimate.md §3.2](cost_estimate.md).

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
| `docs/leaderboard/raw.json`                                   | one row per (fixture, model, setting) — input to the static site |

---

## 7. Common problems

- **`NotImplementedError: no runner for provider X`** — add a runner under [src/runners/](../src/runners/) or remove that entry from `models.yaml`. `openai_compat` already covers OpenAI / DeepSeek / Together / DashScope / xAI / Perplexity via `base_url`.
- **`ValidationError: 'reasoning' does not contain enough characters`** — the model emitted a too-short `reasoning.overall`. The orchestrator retries twice, but if it still fails you'll see `validation_errors` populated. Usually a model-specific prompt tweak fixes it; if not, relax `minLength` in [schemas/prediction.schema.json](../schemas/prediction.schema.json).
- **`leaked_sources` non-empty** — tasks that depend on that source get 0. This is working as designed. Check whether the agent is citing a post-match recap and prompt-engineer it not to (or accept the penalty — that is the whole point of the leakage audit).
- **Clock skew issues with `lock_at_utc`** — all timestamps are UTC. Don't mix local time.

---

## 8. Where next

- [docs/integration.md](integration.md) — "I want my model/agent on this leaderboard" (for third-party developers).
- [docs/cost_estimate.md](cost_estimate.md) — full cost breakdown, per-tier budgets, savings levers.
- [docs/tech_report.md](tech_report.md) — methodology, grading metrics, ablations.
