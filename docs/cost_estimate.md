# WorldCupArena — Cost Estimate

All prices are **approximations as of 2026-04** and should be verified against each vendor's current page before a large run. Figures assume USD.

**Last revised:** 2026-04-18 — roster trimmed to one flagship LLM per provider (Opus / Flash / mini / DeepSeek-V3 / MiroThinker-1.7 dropped).

---

## 1. Token budget (per run)

| Setting | Injected context | ~Input tokens | Runs here |
|---|---|---:|---|
| **S0** | fixture header + schema | 1,200 | closed / open LLMs |
| **S1** | + 23-man squads × 2 | 7,000 | closed / open LLMs |
| **S2** | + squads + form + news + stats | 20,000 | closed / open LLMs |
| **S3** | fixture header, tools on | 1,200 base + tool output | search-LLMs, agents |

Output target per run: **~4,000 tokens** (reasoning block + structured JSON).
S3 tool-use runs: effective input ~3× base.
Agents are billed per run (flat `price_per_run_usd`).

---

## 2. Per-fixture cost — flagship-only roster

### Closed LLMs (S0 + S1 + S2, 3 runs each)

| Model | in / out per 1M | per-fixture |
|---|---|---:|
| GPT-5.4            | $3.00 / $12.00  | $0.23 |
| Claude Sonnet 4.6  | $3.00 / $15.00  | $0.27 |
| Gemini 3 Pro       | $2.00 / $8.00   | $0.15 |
| Grok 4             | $3.00 / $15.00  | $0.27 |
| **Subtotal**       |                 | **$0.92** |

### Open LLMs (3 runs each)

| Model | per-fixture |
|---|---:|
| DeepSeek R1      | $0.05 |
| Qwen3-Max        | $0.12 |
| Llama-4 Maverick | $0.02 |
| **Subtotal**     | **$0.19** |

### Search-enabled LLMs (S3 only, 1 run each)

| Model | per-fixture |
|---|---:|
| Claude Sonnet + search     | $0.12 |
| GPT-5.4 + search           | $0.06 |
| Gemini 3 Pro + search      | $0.04 |
| Perplexity Sonar Pro       | $0.08 |
| **Subtotal**               | **$0.30** |

### Deep Research Agents (S3 only, 1 run each)

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
| Closed LLMs    | $0.92 |
| Open LLMs      | $0.19 |
| Search-LLMs    | $0.30 |
| Agents         | $7.50 |
| **Baseline**   | **$8.91** |
| Format-retry buffer (~15%) | $1.34 |
| **With buffer** | **≈ $10.25** |

### Savings versus previous iterations

| Iteration | per-fixture |
|---|---:|
| Original 6-setting × full roster | $23.60 |
| 4-setting × full roster          | $11.41 |
| **4-setting × flagship-only (this doc)** | **$8.91** |

Cumulative reduction from the original design: **−62 %**.

---

## 3. Per-layer breakdown (T1 – T5)

### 3.1 Per-match call (T1 + T2 + T3 + T4 co-produced)

Output token shares on a sample fully-populated JSON:

| Layer | Output tokens | Share |
|---|---:|---:|
| Reasoning + schema overhead | 650 | 16 % |
| **T1** core result | 400 | 10 % |
| **T2** player level | 1,800 | 45 % |
| **T3** event level | 400 | 10 % |
| **T4** tactics & stats | 400 | 10 % |
| Formatting | 350 | 9 % |

LLM-side attribution of the per-fixture cost (~$1.41 excluding agents):

| Layer | per-fixture $ |
|---|---:|
| Reasoning + overhead | ~$0.23 |
| T1                    | ~$0.14 |
| T2                    | ~$0.63 |
| T3                    | ~$0.14 |
| T4                    | ~$0.14 |
| Formatting            | ~$0.13 |

Agent $7.50 is not meaningfully layer-splittable (one flat-price call emits all layers).

### 3.2 T5 — tournament-level calls

One tournament prediction = one call per model, input ~30k, output ~8k.

| Category | per tournament run |
|---|---:|
| Closed LLMs (4 models)           | $0.74 |
| Open LLMs (3 models)             | $0.24 |
| Search-LLMs (4 models, S3)       | $0.30 |
| Agents (5 models, flat)          | $7.80 |
| **Per tournament run**           | **≈ $9.08** |

T5 frequency options (Phase 2, WC):

| Option | When T5 is re-run | # runs | Phase 2 T5 cost | Δ vs default |
|---|---|---:|---:|---:|
| **Default** | pre-tournament + after each of 4 knockout rounds | 5 | $45.40 | — |
| Reduced-A | pre + post-group + post-R16 + post-QF | 4 | $36.32 | −$9.08 |
| Reduced-B | pre + post-group + post-QF | 3 | $27.24 | −$18.16 |
| **Reduced-C (recommended)** | pre + post-group | 2 | $18.16 | −$27.24 |
| Minimal | pre-tournament only | 1 | $9.08 | −$36.32 |

The absolute savings on T5 frequency are modest (< $40) because the flagship-only roster made T5 cheap. Keep default if the budget allows — more frequent T5 snapshots are useful for measuring how well models update under new information.

---

## 4. Phase totals (flagship-only roster, default T5 frequency)

### Phase 0 — Dry run
One fixture, subset of models → **≈ $2**.

### Phase 1 — UCL semis + final (5 matches)
- 5 × $10.25 per-match = $51
- 1 pre-Phase-1 T5 run (no in-phase re-runs; UCL has no group stage left) = $9
- **Phase 1 total: ≈ $60.**

### Phase 2 — World Cup (64 matches)
- 64 × $10.25 per-match = $656
- T5 default (5 runs): $45
- **Phase 2 total: ≈ $701.**

### Grand totals

| Bucket | Previous flagship-less | Flagship-only |
|---|---:|---:|
| Phase 0                | $3     | $3     |
| Phase 1 (UCL)          | $85    | **$60** |
| Phase 2 (WC)           | $938   | **$701** |
| Infrastructure         | $200   | $200   |
| Buffer (15%)           | $185   | $145   |
| **Total through Jul 2026** | **$1,470** | **≈ $1,109** |

**Net savings from roster simplification: ~$361 (−25 %).**

---

## 5. Cost-reduction levers (on top of the flagship-only baseline)

| Lever | Saving per fixture | Scientific cost |
|---|---:|---|
| **L1** Drop OpenAI DR + Claude Research + Gemini DR (keep MiroThinker H1 + Perplexity DR) | **−$7.00** | less agent diversity |
| **L2** Batch API (OpenAI + Anthropic, 50 % off) for S0/S1/S2 | −$0.35 | 24h turnaround (within lock window) |
| **L3** Prompt caching (system + squads) for S1/S2 | −$0.18 | none |
| **L4** Drop S1 for closed/open LLMs (keep S0 + S2) | −$0.37 | lose "squads-only" datapoint |
| **L5** Tiered coverage: group stage cheap-only, knockouts full | ~$5/group-stage fixture saved | group stage uses reduced roster |
| **L6** Self-host MiroThinker-8B | −$0.30 | operational cost only |
| **L7** T5 Reduced-C (2 runs vs 5) | −$27 total (WC) | 3 fewer full-tournament updates |
| **L8** Cap `max_tokens` + ≤150-word reasoning.overall | −10 % of output spend | already recommended |

---

## 6. Pre-packaged cost tiers (recomputed, flagship-only roster)

| Tier | Levers | $/fixture | Phase 1 | Phase 2 | Infra | Buffer | **Total** |
|---|---|---:|---:|---:|---:|---:|---:|
| **A — Full Publication Run** (this doc's baseline) | none | $10.25 | $60  | $701 | $200 | $145 | **$1,109** |
| **B — Economy**         | L1 + L2 + L3 + L7                | $2.70  | $25  | $195 | $200 | $70  | **$490**   |
| **C — Focused** *(recommended)* | L1 + L2 + L3 + L4 + L7   | $2.33  | $20  | $170 | $200 | $60  | **$450**   |
| **D — Tiered Coverage** | L1–L5 + L7                       | mixed  | $20  | $110 | $200 | $50  | **$380**   |
| **E — Minimal Viable**  | L1–L5 + L7 + self-host           | mixed  | $15  | $80  | $200 | $45  | **$340**   |

### What Tier C looks like concretely

- 4 closed LLMs (GPT-5.4, Sonnet, Gemini 3 Pro, Grok 4) on S0 + S2 — batch-API, caching on.
- 3 open LLMs on S0 + S2.
- 4 search-LLMs on S3.
- 2 agents on S3: MiroThinker H1 + Perplexity DR (cheap survivors).
- T5 pre-tournament + post-group only.
- Format validation + retries (~15 % buffer).
- **Total ≈ $450.**

### Ablation budget

For the tech report, one full-grid ablation on top of Tier C:

- 1 closed (Sonnet) + 1 open (R1) + 1 agent (H1) × full S0/S1/S2/S3 grid × 5 UCL + 1 sample WC group fixture ≈ **+$35**.

**Recommended spend (Tier C + ablation) ≈ $485.**

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
2. **Phase 1 (UCL, end April – May 2026)**: Tier C (~$20/match).
3. **Pre-Phase-2 checkpoint**: review actuals, stay on C or drop to D.
4. **Phase 2 (WC, June 2026)**: Tier C or D across all 64 matches.
5. Stretch: re-run the 5 UCL matches + WC final at Tier A for the technical report.

**Recommended total for a publishable benchmark: ~$450 (Tier C + ablation $485), down from the $2,750 of the original design — 82 % cost reduction.**
