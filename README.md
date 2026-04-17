# WorldCupBench

Benchmarking LLMs and deep-research agents on real-world football prediction — from the tactical "who scores in minute 67" to the strategic "who wins the World Cup."

**Status:** Phase 0 (pipeline dry-run) · 2026-04-17

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
3. **Research Uplift** — score increase from S1 (search on) over S0 (search off).

## Who we test

- **Closed LLMs**: GPT-5 family, Claude Opus/Sonnet 4.x, Gemini 2.5 Pro/Flash, Grok 4.
- **Open LLMs**: DeepSeek V3.2 / R1, Qwen3-Max, Llama-4 Maverick.
- **Search-enabled LLMs**: Claude + web_search, GPT-5 + web_search, Gemini + Google Search, Perplexity Sonar.
- **Deep Research Agents**: OpenAI Deep Research, Gemini Deep Research, Perplexity Deep Research, Claude Research, MiroMind **MiroThinker** 1.7 / H1.
- **Baselines**: Pinnacle closing odds, FiveThirtyEight SPI/Elo, "chalk pick."

See [configs/models.yaml](configs/models.yaml).

## Setting matrix

| | No tools | Search/agent tools |
|---|---|---|
| No info | **S0** | **S1** |
| + official squads | **S2a** | **S2b** |
| + squads + form + news + stats | **S3a** | **S3b** |

See [configs/settings.yaml](configs/settings.yaml).

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
  leaderboard/       static site (GH Pages)
```

## Lifecycle of a fixture

```
 T-48h   ingest.py          pull squads, form, news, odds  →  snapshots/<id>/fixture.json
 T-24h   orchestrator predict  run every (model, setting)  →  predictions/<id>/*.json
 T-1h    lock.py            snapshot_hash frozen, audit sources[] against this moment
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

# Create or fetch a fixture snapshot
python -m src.ingest.api_football --fixture-id 123456 > data/snapshots/demo/fixture.json

# Lock it
python -m src.pipeline.orchestrator lock --fixture data/snapshots/demo/fixture.json

# Predict with all configured models/settings
python -m src.pipeline.orchestrator predict --fixture data/snapshots/demo/fixture.json

# (after kickoff + 24h)
python -m src.pipeline.orchestrator grade --fixture-dir data/snapshots/demo
python -m src.leaderboard.build
```

## Cost

Roughly **$27 per fixture** for the full model roster × all settings. Phase 1 (UCL semis + final) ≈ $155; Phase 2 (World Cup 2026) ≈ $1,900; full project through July 2026 ≈ **$2,750** including infra and buffer. Breakdown in [docs/cost_estimate.md](docs/cost_estimate.md).

## Leakage policy

Every agent/search response must include `sources[].accessed_at`. Any source with `published_at > lock_at_utc` invalidates the tasks that depend on it (0 score). Leakage events are highlighted on the leaderboard.

## Status & roadmap

- [x] Config schema, metrics, orchestrator skeleton
- [x] OpenAI-compat + Anthropic runners
- [ ] Gemini runner, MiroThinker runner, Perplexity/OpenAI DR runners
- [ ] Ingest: squads + news + odds
- [ ] Phase 0 dry run on a Premier League fixture
- [ ] Phase 1: UCL SF1 leg 1 (week of 2026-04-27)
- [ ] Phase 2: Pre-tournament WC prediction (by 2026-06-10)

Contributions welcome — especially new model runners and ingest adapters.

## License

MIT. Predictions, prompts, and grading code are all open; model outputs are attributed to each vendor.
