# WorldCupArena — Cost Estimate

All prices are **approximations as of 2026-04** and should be verified against each vendor's current page before a large run. Figures assume USD.

**Last revised:** 2026-04-18 — setting matrix collapsed from 4 (S0/S1/S2/S3) to 2 (S1 = full context injected, S2 = tools on with self-search guidance). Flagship-only roster retained.

---

## 1. Token budget (per run)

| Setting | Injected context | ~Input tokens | Used by |
|---|---|---:|---|
| **S1** | fixture header + schema + squads + recent form + ~20 news headlines + recent stats | 19,000 | closed / open LLMs |
| **S2** | fixture header + schema + self-search guidance block (examples of each evidence type) | 2,000 base + tool output | search-LLMs, agents |

Output target per run: **~4,000 tokens** (reasoning block + structured JSON).
S2 tool-use runs: effective input ~3× base once tool-call round-trips are included.
Agents are billed per run (flat `price_per_run_usd`), independent of token counts.

Notes on the size change vs the previous 4-setting doc:
- Old S2 injected ~30 news headlines; new S1 caps at 20 (see `src/pipeline/prompt_build.py:NEWS_HEADLINE_CAP`), trimming ~1,000 input tokens.
- New S2 prompt is ~800 tokens larger than old S3 because of the self-search guidance block; offset by fewer total runs.

---

## 2. Per-fixture cost — flagship-only roster, 2 settings

### Closed LLMs (S1 only, 1 run each)

| Model | in / out per 1M | per-fixture |
|---|---|---:|
| GPT-5.4            | $3.00 / $12.00  | $0.11 |
| Claude Sonnet 4.6  | $3.00 / $15.00  | $0.12 |
| Gemini 3 Pro       | $2.00 / $8.00   | $0.07 |
| Grok 4             | $3.00 / $15.00  | $0.12 |
| **Subtotal**       |                 | **$0.42** |

### Open LLMs (S1 only, 1 run each)

| Model | per-fixture |
|---|---:|
| DeepSeek R1      | $0.02 |
| Qwen3-Max        | $0.06 |
| Llama-4 Maverick | $0.01 |
| **Subtotal**     | **$0.09** |

### Search-enabled LLMs (S2 only, 1 run each)

| Model | per-fixture |
|---|---:|
| Claude Sonnet + search     | $0.14 |
| GPT-5.4 + search           | $0.07 |
| Gemini 3 Pro + search      | $0.05 |
| Perplexity Sonar Pro       | $0.09 |
| **Subtotal**               | **$0.35** |

### Deep Research Agents (S2 only, 1 run each)

| Agent | per-fixture |
|---|---:|
| OpenAI Deep Research         | $3.00 |
| Gemini Deep Research         | $2.00 |
| Perplexity Deep Research     | $0.20 |
| Claude Research (Sonnet)     | $2.00 |
| MiroThinker H1               | $0.30 |
| **Subtotal**                 | **$7.50** |

### Per-fixture grand total

| Category | per-fixture |
|---|---:|
| Closed LLMs    | $0.42 |
| Open LLMs      | $0.09 |
| Search-LLMs    | $0.35 |
| Agents         | $7.50 |
| **Baseline**   | **$8.36** |
| Format-retry buffer (~15%) | $1.25 |
| **With buffer** | **≈ $9.61** |

### Savings versus previous iterations

| Iteration | per-fixture |
|---|---:|
| Original 6-setting × full roster                    | $23.60 |
| 4-setting × full roster                             | $11.41 |
| 4-setting × flagship-only roster                    | $8.91  |
| **2-setting × flagship-only roster (this doc)**     | **$8.36** |

Concrete savings from the 4→2 setting collapse (holding the flagship roster fixed):
- Closed LLMs: $0.92 → $0.42 per fixture (−$0.50)
- Open LLMs:   $0.19 → $0.09 per fixture (−$0.10)
- Search-LLMs: $0.30 → $0.35 per fixture (+$0.05, longer S2 prompt)
- Agents:      $7.50 (unchanged — 1 run either way)
- **Net:** −$0.55 per fixture.

Over the benchmark (5 UCL + 64 WC matches + T5 calls), this is roughly **−$40–$45** — modest in absolute terms because deep-research agents dominate the bill, but also free: the two dropped settings (old S0 "no info, no tools" and old S3 "tools but unprompted") answered questions we weren't measuring.

Cumulative reduction from the original design: **−65 %**.

---

## 3. Per-layer breakdown (T1 – T5)

### 3.1 Per-match call (T1 + T2 + T3 + T4 co-produced)

Output token shares on a sample fully-populated JSON (unchanged — output structure did not change):

| Layer | Output tokens | Share |
|---|---:|---:|
| Reasoning + schema overhead | 650 | 16 % |
| **T1** core result | 400 | 10 % |
| **T2** player level | 1,800 | 45 % |
| **T3** event level | 400 | 10 % |
| **T4** tactics & stats | 400 | 10 % |
| Formatting | 350 | 9 % |

LLM-side attribution of the per-fixture LLM cost (~$0.86 excluding agents):

| Layer | per-fixture $ |
|---|---:|
| Reasoning + overhead | ~$0.14 |
| T1                    | ~$0.09 |
| T2                    | ~$0.39 |
| T3                    | ~$0.09 |
| T4                    | ~$0.09 |
| Formatting            | ~$0.08 |

Agent $7.50 is not meaningfully layer-splittable (one flat-price call emits all layers).

### 3.2 T5 — tournament-level calls

One tournament prediction = one call per model, input ~30k, output ~8k. T5 uses the same S1/S2 split as per-match calls:

| Category | per tournament run |
|---|---:|
| Closed LLMs (4 models, S1)        | $0.74 |
| Open LLMs (3 models, S1)          | $0.24 |
| Search-LLMs (4 models, S2)        | $0.32 |
| Agents (5 models, flat)           | $7.80 |
| **Per tournament run**            | **≈ $9.10** |

T5 frequency options (Phase 2, WC):

| Option | When T5 is re-run | # runs | Phase 2 T5 cost | Δ vs default |
|---|---|---:|---:|---:|
| **Default** | pre-tournament + after each of 4 knockout rounds | 5 | $45.50 | — |
| Reduced-A | pre + post-group + post-R16 + post-QF | 4 | $36.40 | −$9.10 |
| Reduced-B | pre + post-group + post-QF | 3 | $27.30 | −$18.20 |
| **Reduced-C (recommended)** | pre + post-group | 2 | $18.20 | −$27.30 |
| Minimal | pre-tournament only | 1 | $9.10 | −$36.40 |

---

## 4. Phase totals (flagship-only roster, 2 settings, default T5 frequency)

### Phase 0 — Dry run
One fixture, subset of models → **≈ $2**.

### Phase 1 — UCL semis + final (5 matches)
- 5 × $9.61 per-match = $48
- 1 pre-Phase-1 T5 run (no in-phase re-runs; UCL has no group stage left) = $9
- **Phase 1 total: ≈ $57.**

### Phase 2 — World Cup (64 matches)
- 64 × $9.61 per-match = $615
- T5 default (5 runs): $46
- **Phase 2 total: ≈ $661.**

### Grand totals

| Bucket | 4-setting flagship | **2-setting flagship** |
|---|---:|---:|
| Phase 0                | $3     | $3     |
| Phase 1 (UCL)          | $60    | **$57** |
| Phase 2 (WC)           | $701   | **$661** |
| Infrastructure         | $200   | $200   |
| Buffer (15%)           | $145   | $138   |
| **Total through Jul 2026** | $1,109 | **≈ $1,059** |

**Net savings from the setting collapse: ~$50 (−5 %).** Combined with the earlier roster simplification, cumulative reduction from the original design is now **~$1,700 (−62 %)**.

---

## 5. Cost-reduction levers (on top of this baseline)

| Lever | Saving per fixture | Scientific cost |
|---|---:|---|
| **L1** Drop OpenAI DR + Claude Research + Gemini DR (keep MiroThinker H1 + Perplexity DR) | **−$7.00** | less agent diversity |
| **L2** Batch API (OpenAI + Anthropic, 50 % off) for S1 | −$0.13 | 24h turnaround (within lock window) |
| **L3** Prompt caching (system + squads) for S1 | −$0.10 | none |
| **L4** Tiered coverage: group stage cheap-only, knockouts full | ~$5/group-stage fixture saved | group stage uses reduced roster |
| **L5** Self-host MiroThinker-8B | −$0.30 | operational cost only |
| **L6** T5 Reduced-C (2 runs vs 5) | −$27 total (WC) | 3 fewer full-tournament updates |
| **L7** Cap `max_tokens` + ≤150-word reasoning.overall | −10 % of output spend | already recommended |

(There is no longer an "L drop S1" lever — S1 is now the *only* non-tool setting, so dropping it would leave the non-tool arm empty.)

---

## 6. Pre-packaged cost tiers

| Tier | Levers | $/fixture | Phase 1 | Phase 2 | Infra | Buffer | **Total** |
|---|---|---:|---:|---:|---:|---:|---:|
| **A — Full Publication Run** (this doc's baseline) | none | $9.61 | $57  | $661 | $200 | $138 | **$1,059** |
| **B — Economy**         | L1 + L2 + L3 + L6                | $2.55 | $20  | $180 | $200 | $60  | **$460**   |
| **C — Focused** *(recommended)* | L1 + L2 + L3 + L6 + caching aggressive | $2.25  | $18  | $160 | $200 | $55  | **$435**   |
| **D — Tiered Coverage** | L1–L4 + L6                       | mixed  | $18  | $105 | $200 | $48  | **$370**   |
| **E — Minimal Viable**  | L1–L5 + L6 + self-host           | mixed  | $14  | $78  | $200 | $42  | **$335**   |

### What Tier C looks like concretely

- 4 closed LLMs (GPT-5.4, Sonnet, Gemini 3 Pro, Grok 4) on **S1** — batch-API, caching on.
- 3 open LLMs on **S1**.
- 4 search-LLMs on **S2**.
- 2 agents on **S2**: MiroThinker H1 + Perplexity DR (cheap survivors).
- T5 pre-tournament + post-group only.
- Format validation + retries (~15 % buffer).
- **Total ≈ $435.**

### Ablation budget

For the tech report, one full-grid ablation on top of Tier C:

- 1 closed (Sonnet) + 1 open (R1) + 1 agent (H1) × both settings × 5 UCL + 1 sample WC group fixture ≈ **+$25**.

**Recommended spend (Tier C + ablation) ≈ $460.**

---

## 7. Non-API costs

| Item | Monthly | Notes |
|---|---:|---|
| API-Football Pro | $50 | 75k req/day. |
| football-data.org | $0 | Free backup. |
| GitHub Actions | $0 | Free tier. |
| GitHub Pages | $0 | Static leaderboard. |
| transfermarkt / FBref / FotMob | $0 | Scraped. |
| Pinnacle / Betfair odds | $0–$30 | Scrape or odds-API tier. |

Total infra: ≤ $100/mo → ≈ $200 through the benchmark window.

---

## 8. Verification plan

Before Phase 1 kickoff, run a **single-fixture dry run at Tier C economics (~$3)** and log real `input_tokens` / `output_tokens` per API. Replace §2/§3 estimates with actuals.

A ready-to-use dry run exists: `scripts/dryrun_bayern_madrid.sh` — a completed UCL QF fixture used only to exercise the pipeline (leakage does not matter for dry-runs).

---

## 9. Recommended path

1. **Now**: `scripts/dryrun_bayern_madrid.sh` — validate pipeline (~$2).
2. **Phase 1 (UCL, end April – May 2026)**: Tier C (~$18/match).
3. **Pre-Phase-2 checkpoint**: review actuals, stay on C or drop to D.
4. **Phase 2 (WC, June 2026)**: Tier C or D across all 64 matches.
5. Stretch: re-run the 5 UCL matches + WC final at Tier A for the technical report.

**Recommended total for a publishable benchmark: ~$435 (Tier C + ablation $460), down from the $2,750 of the original design — 83 % cost reduction.**
