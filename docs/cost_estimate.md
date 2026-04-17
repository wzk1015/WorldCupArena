# WorldCupBench — Cost Estimate

All prices are **approximations as of 2026-04** and should be verified against each vendor's current page before a large run. Figures assume USD.

---

## 1. Per-call token budget (assumptions)

Inputs vary by Setting:

| Setting | Injected context | ~Input tokens | Notes |
|---|---|---:|---|
| S0  | fixture header + schema | **1,200** | schema alone ~1k tokens |
| S1  | same as S0; search tool on | 1,200 | agent/search-llm fetches add runtime tokens |
| S2a | + 23-man squads × 2 | **7,000** | squad JSON is the bulk |
| S2b | same; search on | 7,000 | |
| S3a | + recent form + news + stats | **20,000** | news headlines alone ~8k |
| S3b | same; search on | 20,000 | |

Output target per run: **~4,000 tokens** (structured JSON covering all sub-tasks + ~300-word reasoning). Reasoning-heavy models (Claude Opus, DeepSeek-R1) may emit 6–10k output tokens via thinking traces.

For search/agent runs, tool output adds ~3–10× the base input tokens because fetched article text is appended to context. Effective multipliers used below:

| Model type | Input multiplier (tools on) | Output multiplier |
|---|---:|---:|
| Plain LLM (no tools) | 1.0 | 1.0 |
| Search-enabled LLM  | 3.0 | 1.2 |
| Deep Research Agent | flat `price_per_run_usd` (see models.yaml) | — |

---

## 2. Per-model, per-fixture cost

Table shows cost of running **all six Settings** (S0, S1, S2a, S2b, S3a, S3b) where supported. Plain LLMs only run S0/S2a/S3a; search-enabled variants only run S1/S2b/S3b; agents only run S1 and S3b.

Formula for token-billed models (per run):

```
cost = input_tokens × $in_price + output_tokens × $out_price
```

### Closed LLMs — 3 no-tool settings each (S0 + S2a + S3a)

```
input ≈ 1,200 + 7,000 + 20,000 = 28,200 tok
output ≈ 3 × 4,000 = 12,000 tok
```

| Model | per-fixture (3 runs) |
|---|---:|
| GPT-5              | $0.19 |
| GPT-5-mini         | $0.03 |
| Claude Opus 4.7    | $1.32 |
| Claude Sonnet 4.6  | $0.27 |
| Gemini 2.5 Pro     | $0.10 |
| Gemini 2.5 Flash   | $0.04 |
| Grok 4             | $0.27 |
| **Subtotal**       | **$2.22** |

### Open LLMs — 3 no-tool settings each

| Model | per-fixture |
|---|---:|
| DeepSeek V3.2          | $0.02 |
| DeepSeek R1 (reasoner) | $0.05 |
| Qwen3-Max              | $0.12 |
| Llama-4 Maverick       | $0.02 |
| **Subtotal**           | **$0.21** |

### Search-enabled LLMs — 3 search settings each (S1 + S2b + S3b)

Use input multiplier 3×. Input ≈ 84,600 tok; output ≈ 14,400 tok. Anthropic web_search adds $10 per 1k searches; assume ~15 searches per run = $0.15/run extra.

| Model | per-fixture (3 runs) |
|---|---:|
| Claude Opus w/search   | $1.27 + $2.59 search-overhead = **$3.86** |
| GPT-5 w/search         | $0.36 |
| Gemini 2.5 Pro search  | $0.18 |
| Perplexity Sonar Pro   | $0.47 |
| **Subtotal**           | **$4.87** |

### Deep Research Agents — 2 settings each (S1 + S3b)

Priced per run from models.yaml:

| Agent | per-fixture (2 runs) |
|---|---:|
| OpenAI Deep Research         | $6.00 |
| Gemini Deep Research         | $4.00 |
| Perplexity Deep Research     | $0.40 |
| Claude Research              | $5.00 |
| MiroThinker 1.7              | $0.30 |
| MiroThinker H1               | $0.60 |
| **Subtotal**                 | **$16.30** |

### Per-fixture total (all categories, all supported settings)

| Category | per-fixture |
|---|---:|
| Closed LLMs         | $2.22 |
| Open LLMs           | $0.21 |
| Search-LLMs         | $4.87 |
| Deep Research       | $16.30 |
| **Grand total**     | **≈ $23.60** |

Add ~15 % buffer for retries, failed parses, schema-validation re-asks → **≈ $27 per fixture**.

---

## 3. Phase totals

### Phase 0 — Dry run (1 non-target fixture, subset of models)
Scope: 2 closed LLMs + 1 search LLM + 1 agent, S0/S2a/S3a only → **~$3**.

### Phase 1 — UCL semis + final (6 prediction events)
- SF1 leg 1, SF1 leg 2, SF2 leg 1, SF2 leg 2, Final = 5 matches.
- Plus one "whole-tournament" pre-SF prediction (T5 only, lighter) ≈ $20.
- 5 × $27 + $20 = **≈ $155**.

### Phase 2 — World Cup 2026

64 matches. For each we want:
1. A **pre-tournament** prediction (once, all 64 matches in one tournament-level call — run T5 tasks, ~$40 total).
2. A **per-match** prediction at T-1h × 64 = $27 × 64 = **$1,728**.
3. After each round, a **re-prediction** of remaining knockouts ≈ 4 re-runs of tournament-level call = $160.

Subtotal: **~$1,928**.

### Grand totals

| Phase | Estimate |
|---|---:|
| Phase 0 | $3 |
| Phase 1 (UCL) | $155 |
| Phase 2 (WC) | $1,928 |
| Infra (API-Football Pro, Pinnacle/Betfair odds scrape) | ~$200 |
| Buffer (20 %) | ~$460 |
| **Total through July 2026** | **~$2,750** |

Fidelity knobs (will *increase* cost):
- Run each model N=3 times and average (stochastic) → 3× cost on LLMs.
- Add a "re-predict at T-15m" round → ~1.2× cost.

Cost-reduction levers are detailed in **§6**, pre-packaged tiers in **§7**.

---

## 4. Non-API costs

| Item | Monthly | Notes |
|---|---:|---|
| API-Football Pro | $50 | 75k req/day; enough for ingest + ground truth. |
| football-data.org | $0 | Free backup tier. |
| GitHub Actions | $0 | Free tier fits < 90 min/fixture × few dozen runs/mo. |
| GitHub Pages | $0 | Static leaderboard. |
| transfermarkt / FBref / FotMob | $0 | Scraped, no API. |
| Storage (DuckDB + artifacts) | $0 | < 5 GB through season. |
| Pinnacle / Betfair odds | $0–$30 | Free scrape or odds-API tier. |

Total infra: **≤ $100/mo**, so ~$300 through the benchmark period.

---

## 5. Verification plan

Before Phase 1 kickoff, run a **single-fixture dry run** and log real `input_tokens`/`output_tokens` returned by each API. Replace the estimates here with actuals and re-price. Because reasoning/thinking-heavy models easily 2× the output estimate, this calibration step is load-bearing.

---

## 6. Cost-reduction levers

Where the money goes in the $27/fixture baseline:

```
Deep Research Agents   $16.30   ~60%   <-- #1 target
Search-enabled LLMs    $ 4.87   ~18%
Closed LLMs            $ 2.22   ~ 8%
Open LLMs              $ 0.21   ~ 1%
Tool / search overhead $ 3.40   ~13%
```

Deep Research Agents dominate. Any serious cost plan starts there.

### L1 — Prune the expensive Deep Research agents

Keep MiroThinker (1.7 + H1) + Perplexity Deep Research. Drop the $3–5/run trio:

| Dropped | Savings per fixture |
|---|---:|
| OpenAI Deep Research ($6) | −$6.00 |
| Claude Research ($5)      | −$5.00 |
| Gemini Deep Research ($4) | −$4.00 |
| **L1 total**              | **−$15.00** |

Scientific cost: we lose diversity in the "Research Uplift" leaderboard, but MiroThinker H1 + Perplexity DR already span the open/closed axis. Acceptable for Phase 1 and group-stage Phase 2; reinstate for knockouts.

**Per-fixture after L1: $12.00**. Phase 2 savings: ~$960.

### L2 — Batch API (OpenAI + Anthropic, 50 % off, 24h turnaround)

T-24h prediction lock is well within the 24h batch window, so we can use:
- OpenAI Batch API: 50 % off input + output.
- Anthropic Message Batches API: 50 % off both.

Applies only to **non-search** runs (batch APIs don't allow streaming tools). Savings on closed LLM portion:

| Model | per-fixture saving |
|---|---:|
| GPT-5 family            | −$0.11 |
| Claude Opus/Sonnet       | −$0.80 |
| Gemini (no batch discount equivalent) | 0 |
| Grok                    | −$0.14 |
| **L2 total**            | **−$1.05** |

**After L1+L2: $10.95 / fixture.**

### L3 — Prompt caching (Anthropic, OpenAI, Gemini)

The system prompt (~1k tokens) and squads block (~5k tokens) are identical across every setting for a given fixture; the system prompt is also identical *across fixtures*. All three major vendors offer cache-read at ~10 % of full input price.

Realistic savings with caching on S2a/S2b/S3a/S3b (the 4 settings that inject squads):

| Vendor portion | per-fixture saving |
|---|---:|
| Claude (Opus+Sonnet, 4 cached settings) | −$0.35 |
| GPT-5 family                             | −$0.08 |
| Gemini                                   | −$0.05 |
| **L3 total**                             | **−$0.48** |

**After L1+L2+L3: $10.47 / fixture.**

### L4 — Trim the Setting matrix

The 6-cell matrix is for *research clarity*, not every model needs every cell. Proposed cuts:

- **Closed/open LLMs**: run only **S0** and **S3a** (drop S2a). Rationale: S0 and S3a bracket the "context uplift" axis cleanly; S2a is an intermediate we can drop.
- **Search-enabled LLMs**: run only **S3b** (drop S1 and S2b). Rationale: once search is on, the no-context setting adds little info vs. the full-context one.
- **Deep Research Agents**: run only **S3b** (drop S1).

Impact:

| Category | was | now | saving |
|---|---:|---:|---:|
| Closed LLMs (3 → 2 settings) | $2.22 | $1.48 | −$0.74 |
| Open LLMs (3 → 2 settings)   | $0.21 | $0.14 | −$0.07 |
| Search-LLMs (3 → 1 setting) with L1 applied | $4.87 | $1.62 | −$3.25 |
| Agents (2 → 1 setting) with L1 applied    | $1.30 | $0.65 | −$0.65 |
| **L4 total**                 |       |      | **−$4.71** |

Scientific cost: the "Research Uplift = S1 − S0" metric now uses S3b − S0 instead, so it blends research effect with context effect. Fine for headline numbers; for research-quality ablation, run S0/S1/S3a/S3b on **one representative pair of models** (e.g. Claude + MiroThinker) and the rest stays 2-cell.

**After L1..L4: $5.76 / fixture.**

### L5 — Tiered match coverage (Phase 2 only)

Not every World Cup match is equally informative. Proposal:

- **Knockouts (16 matches)** — full roster with L1..L4 applied: $5.76 each.
- **Group stage (48 matches)** — "cheap-only" roster: 4 open LLMs + MiroThinker 1.7 + Perplexity DR at $0.90 each.

Phase 2 match-level subtotal: 16 × $5.76 + 48 × $0.90 = $92 + $43 = **$135** (vs. $1,728 in Tier A).

### L6 — Self-host MiroThinker 8B

Available open-weight; with a $0.30/h GPU can serve ~2 req/s. Replaces hosted MiroThinker 1.7. Savings small in absolute dollars (~$0.15/fixture) but removes MiroMind API dependency for Phase 2 scale. Operational cost only — not recomputed in the tiers below.

### L7 — Drop intermediate tournament re-predictions

Current plan: full-tournament re-prediction after every round = 4 × $40 = $160.
Reduced plan: re-predict only after group stage + after QF = 2 × $40 = $80. Saving: **−$80**.

### L8 — Cap output tokens + suppress redundant reasoning

For thinking-native models (Claude Opus, DeepSeek-R1, Gemini 2.5 Pro "thinking"), `reasoning` field in the JSON output often duplicates 2–3k tokens of internal thinking. Cap `max_tokens=4096` and ask for ≤150-word `reasoning`. Realistic saving: ~15 % of output-token spend on thinking-native models. Already assumed in baseline; call out as "do not relax."

### L9 — Reduce model count to one flagship per vendor

Drop `gpt-5-mini` (keep GPT-5), `gemini-2.5-flash` (keep Pro), `claude-opus-4-7` (keep Sonnet for plain-LLM; keep Opus only for search if kept at all). Saves diversity but also correlated-error checking. Per-fixture saving ~$1.10, but harder to justify for research value. Optional lever; not bundled into default tiers.

---

## 7. Pre-packaged cost tiers

| Tier | Levers applied | $ / fixture (full roster) | Phase 1 | Phase 2 | Infra | Buffer | **Total** |
|---|---|---:|---:|---:|---:|---:|---:|
| **A — Full Publication Run** (as designed)           | —                  | $27.00 | $155  | $1,928 | $200 | $460 | **$2,750** |
| **B — Economy**                                        | L1 + L2 + L3       | $10.47 | $75   | $710   | $200 | $200 | **$1,190** |
| **C — Focused** *(recommended)*                        | L1..L4 + L7        | $ 5.76 | $45   | $215   | $200 | $90  | **$550**   |
| **D — Tiered Coverage**                                | L1..L5 + L7        | mixed  | $45   | $135   | $200 | $75  | **$460**   |
| **E — Minimal Viable**                                 | L1..L5 + L7 + L9   | mixed  | $30   | $90    | $200 | $60  | **$380**   |

Phase 1 figures assume all 5 UCL matches use the full roster (no tiered coverage for such a small set).

### What each tier actually looks like

**Tier C (recommended)** — our default "ship it" configuration:

- 7 closed LLMs on S0 + S3a (batch-API, cached).
- 4 open LLMs on S0 + S3a.
- 4 search-LLMs on S3b only (Opus-search dropped).
- 3 Deep Research agents on S3b only: MiroThinker 1.7, MiroThinker H1, Perplexity DR.
- Full tournament re-prediction only after group stage and after QF.
- **3 leaderboards preserved**; Research Uplift computed as S3b − S3a on matched models.
- Scientific ablation (S0/S1/S2a/S2b/S3a/S3b full grid) run on **one closed + one open + one agent** = 3 models × 6 settings × 5 UCL matches + one sample WC group-stage fixture ≈ +$80 on top.
- **Total ≈ $550 + $80 = $630.**

**Tier D (tiered coverage)** — cut group-stage rigor:

- Tier C for all 5 UCL matches and all 16 WC knockouts.
- Group stage (48 matches): open LLMs + MiroThinker 1.7 + Perplexity DR only, ~$0.90 each.
- Still produces a full 64-match leaderboard; group stage rankings carry a "cheap-roster" badge.
- **Total ≈ $460.**

**Tier E (minimal viable)** — if budget really tight:

- One flagship per vendor (GPT-5, Claude Sonnet, Gemini Pro, DeepSeek R1, Qwen3, Llama4, Grok).
- Two search-LLMs: Gemini-search + Perplexity Sonar.
- Two agents: MiroThinker H1 + Perplexity DR.
- S0 + S3a for non-search, S3b for search. No re-predictions beyond post-group.
- Knockouts full, group stage cheap-only.
- **Total ≈ $380.**

### Sanity check: what's the floor?

An *absolute floor* keeping the benchmark meaningful would be:
- 1 flagship LLM (GPT-5 or Claude Sonnet) on S0 + S3a.
- 1 search-LLM (Perplexity Sonar) on S3b.
- 1 Deep Research agent (MiroThinker H1) on S3b.
- All 5 UCL matches + only WC knockouts (16 matches) + 1 pre-tournament run.

Per-fixture cost: ~$1.80. Total: 21 × $1.80 + $40 = **$78**. Plus $200 infra = **~$280**. This is roughly the lower bound of a publishable benchmark; below this we lose the "many models, many settings" story.

---

## 8. Recommended path

1. **Now**: Phase 0 dry-run at **Tier C economics** (~$5 to validate pipeline on one fixture).
2. **Phase 1 (UCL)**: run at **Tier C** to get real data and refine prices (~$45).
3. **Decide for Phase 2**: pick Tier C vs. Tier D based on Phase 1 actual costs.
   - If Phase 1 comes in under estimate, go Tier C across all 64 matches.
   - If it overshoots, drop to Tier D.
4. Keep Tier A as a **stretch goal** for the final technical report, re-running the 5 UCL matches + the WC final at full roster so we have one apples-to-apples slice for the paper.

Net: the benchmark is publishable at **$380–$630** (Tier C or D). Tier A's $2,750 is a "reviewer-proof completeness" number, not a required spend.
