# ⚽️🤖 WorldCupArena

Benchmarking LLMs and deep-research agents on real-world football prediction — from the tactical "who scores in minute 67" to the strategic "who wins the World Cup."

**Check the [website](https://wzk1015.github.io/WorldCupArena/) for leaderboard and predictions!**

**Docs**: [Usage](docs/usage.md) · [Automation](docs/automation.md) · [Integration](docs/integration.md) ·[Announcement](docs/announcement.md) · [中文宣传](docs/promo_zh.md)

---

## Why

Existing LLM benchmarks test static knowledge or isolated reasoning. **Football prediction** requires multi-source real-time retrieval (injury news, tactical reports, odds), integrated reasoning over heterogeneous signals, and produces ground truth on a fixed schedule. It is therefore an ideal testbed for deep-research agents vs. plain LLMs.

Unlike weather or stock prediction, football also has rich sub-structure (lineups, in-match events, season-long standings) so a single match yields many evaluation signals.

## What we measure

| Layer | Task examples | Primary metric |
|---|---|---|
| **T1 Core result** (35%) | 1X2 probabilities, score distribution, advancement | Brier, RPS |
| **T2 Player level** (25%) | starting XI, goalscorers, formations, MOTM | Jaccard, F1+nDCG |
| **T3 Event level** (15%) | goal minute, subs, cards, penalties | Hungarian-matched MAE, event-F1 |
| **T4 Tactics & stats** (15%) | possession, xG, shots, passes, defensive actions | sMAPE |
| **T5 Tournament macro** (10%) | group standings, bracket, champion, top scorer | Kendall τ, bracket score |

Composite score ∈ [0, 100]. Three leaderboards:

1. **Main** — overall composite.
2. **Above-Market** — composite gain vs. Pinnacle closing odds.
3. **Research Uplift** — score increase from S2 (tool-using agent, self-search) over S1 (LLM with the full injected context pack).

## Who we test

Currently we support the following models (defined in [configs/models.yaml](configs/models.yaml)):

- **Closed LLMs**: GPT-5.4, Claude Opus 4.7, Gemini 3.1 Pro.
- **Search-enabled LLMs**: GPT-5.4 + web_search, Claude Opus 4.7 + web_search, Gemini 3.1 Pro + google_search.

TODO:

- **Open LLMs**: DeepSeek R1, Qwen3-Max, Llama-4 Maverick. *(Currently via hosted endpoints; swap to self-hosted vLLM by setting `base_url`.)*
- **Deep Research Agents**: OpenAI Deep Research, Gemini Deep Research, Perplexity Deep Research, Claude Research, MiroMind MiroThinker H1.
- **Baselines**: Pinnacle closing odds, FiveThirtyEight SPI/Elo, "chalk pick."


Every model entry in [configs/models.yaml](configs/models.yaml) supports a `base_url` field for routing through proxy / 中转 endpoints.

## Setting matrix

Two settings — one for non-tool LLMs, one for tool-using models / agents:

| Setting | Injected context | Tools | Run by |
|---|---|---|---|
| **S1** | full context pack (squads + recent form + ~20 news headlines + recent stats) | off | closed / open LLMs |
| **S2** | fixture header + self-search guidance block (with worked examples of each evidence type) | **on** | search-LLMs + deep-research agents |

See [configs/settings.yaml](configs/settings.yaml). S1 measures "best case with injected evidence"; S2 measures "best case with self-directed retrieval". Research uplift = S2 − S1.

## Repo layout

```
configs/       models, settings, tasks + weights
schemas/       prediction + fixture JSON schemas
prompts/       system + task templates (bilingual)
src/
  ingest/      API-Football, transfermarkt, odds
  runners/     one file per provider (openai_compat, anthropic, ...)
  graders/     metrics + per-match grader
  pipeline/    orchestrator, prompt_build, lock/audit
  leaderboard/ aggregate → static site
data/
  snapshots/<fixture_id>/fixture.json    frozen pre-match state
  snapshots/<fixture_id>/truth.json      filled in post-match
  predictions/<fixture_id>/*.json        raw per-model outputs
  results/<fixture_id>/*.json            scored outputs
.github/workflows/   predict / grade / leaderboard-build
docs/
  cost_estimate.md   per-fixture and per-phase $$ estimates
  tech_report.md     methodology + results
  announcement.md    promotional write-up
  site/              static site (GH Pages)
```

## Lifecycle of a fixture

```
 T-48h   ingest.py          pull squads, form, news, odds  →  snapshots/<id>/fixture.json
 T-24h   lock.py + predict  snapshot_hash frozen; run every (model, setting)  →  predictions/<id>/*.json
 T+3h    ingest/result      pull goals, lineups, stats     →  snapshots/<id>/truth.json
 T+24h   orchestrator grade → results/<id>/*.json
         leaderboard.build  → docs/leaderboard/
```

All API keys live in `.env` locally, or GitHub Actions secrets in CI.

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill in API keys

python -m src.pipeline.scheduler show
python -m src.pipeline.scheduler tick
```

Full step-by-step usage (ingest → lock → predict → grade → leaderboard) lives in [docs/usage.md](docs/usage.md).

Want your model on the leaderboard? See [docs/integration.md](docs/integration.md) — most integrations take less than 10 minutes.

## Cost

With the flagship-only roster: **~$10 per fixture** with format-retry buffer. Phase 1 (UCL semis + final) ≈ $60; Phase 2 (World Cup 2026) ≈ $701; full project through July 2026 ≈ **$1,109** at full roster, or **~$450 at recommended Tier C** (economy levers + caching + tiered T5). Full breakdown — including per-layer T1–T5 costs and T5 frequency options — in [docs/cost_estimate.md](docs/cost_estimate.md).

## Leakage policy

Every agent/search response must include `sources[].accessed_at`. Any source with `published_at > lock_at_utc` invalidates the tasks that depend on it (0 score). Leakage events are highlighted on the leaderboard.

## Format integrity

Every prediction is **schema-validated + semantically checked** at submission time:
- JSON Schema conformance (required fields, enums, patterns).
- `win_probs` and `score_dist` probability sums normalized to 1 (within 1e-2).
- `lineups.*.starting` has exactly 11 players.
- `stats` contains all 8 required keys with `{home, away}` pairs.
- `reasoning.overall` non-empty and ≥80 characters (reasoning comes *first* in the JSON, before numeric fields).

If validation fails, the orchestrator sends a targeted repair prompt to the same model (up to 2 retries) so we never discover malformed output only after kickoff.

## Status & roadmap

- [x] Config schema, metrics, orchestrator skeleton
- [x] OpenAI-compat + Anthropic runners
- [x] Gemini runner, MiroThinker runner, Perplexity/OpenAI DR runners
- [x] Ingest: squads + news + odds
- [x] Phase 0 dry run on a Premier League fixture
- [ ] Phase 1: UCL SF1 leg 1 (week of 2026-04-27)
- [ ] Phase 2: Pre-tournament WC prediction (by 2026-06-10)

Contributions welcome — especially new model runners and ingest adapters. See [docs/integration.md](docs/integration.md) for model-maintainer onboarding.

Sponsorship welcome for API cost and deployment of open-source models.

## License

MIT. Predictions, prompts, and grading code are all open; model outputs are attributed to each vendor.

## Citation

```
@misc{worldcuparena,
  author = {Zhaokai Wang},
  title = {WorldCupArena},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/wzk1015/WorldCupArena}}
}
```