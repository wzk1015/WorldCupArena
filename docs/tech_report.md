# WorldCupArena — Technical Report

*Draft, 2026-04-17. Replaced with empirical results at end of Phase 1 and Phase 2.*

---

## 1. Motivation

Three gaps in current LLM benchmarks:

1. **Static knowledge only.** Most benchmarks (MMLU, GPQA, HLE) test training-cutoff facts. Real-world tasks require retrieval of post-training information.
2. **Single-source reasoning.** Tool-use benchmarks usually provide one clean source. Real deep-research spans heterogeneous sources that disagree (official lineups, rumour-mill news, odds, stats).
3. **Subjective evaluation.** Long-form evaluation relies on LLM-as-judge or human rating. Football produces **objective, high-dimensional ground truth** on a predictable calendar.

WorldCupArena operationalises "deep research for prediction" with quantitative metrics at five granularities (match outcome → event-level → stats).

## 2. Related work

- **Sports-forecasting literature**: Constantinou & Fenton (Bayesian nets for football), 538's SPI/Club SPI, Dixon–Coles Poisson models. We borrow Brier/RPS as our primary probability scoring rule.
- **LLM agent benchmarks**: GAIA, BrowseComp, AssistantBench. BrowseComp, in particular, measures retrieval-heavy tasks; WorldCupArena extends that to **temporal**, **multi-event** forecasting where the answer is only revealed in the future.
- **MiroThinker** (MiroMind, 2026) reports 74.0 / 88.2 on BrowseComp and BrowseComp-ZH at ~$0.07/call; we include it as a strong low-cost deep-research baseline.

## 3. Task taxonomy

Five layers × sub-tasks (see `configs/tasks.yaml`). Each sub-task names an `output_field` on the prediction JSON and a `metric` (one of the primitives in `src/graders/metrics.py`). Weights:

```
Layer weights: 0.35 / 0.25 / 0.15 / 0.15 / 0.10
within-layer weights: see configs/tasks.yaml
```

## 4. Metric definitions

### 4.1 Probability

- **Brier (3-way)**: `1 − ||p − y||² / 2`, scaled to 0–100.
- **Brier (binary/multiclass)**: natural generalisation.
- **RPS on score distribution**: collapse predicted score distribution to 1X2 marginal, then Brier. Stricter predictors (say, Poisson samplers) are rewarded.

### 4.2 Regression

- **sMAPE**: `1 − |p−t| / ((|p|+|t|)/2)`. Robust to zero ground-truth stats.
- **Goal-diff MAE**: capped at 5 (errors beyond 5 are indistinguishable in practice).

### 4.3 Set / classification

- **Jaccard + position** for lineups: 70 % name overlap, 30 % name+position overlap.
- **F1 + nDCG** for goalscorers: F1 on the set, then nDCG@3 on the top-ranked predictions (probability-sorted).
- **Exact match** for formations.
- **Top-1 accuracy** for MOTM / awards.

### 4.4 Event matching

Goals, subs, cards live in time. We run **Hungarian assignment** between predicted and actual events using a cost that combines

```
cost(i,j) = |minute_pred - minute_true| + (0 if same actor else 30)
```

Unmatched predicted events incur a flat 30-minute penalty. Final score = `max(0, 100 − avg_cost)`. This rewards getting the actors right even when timing is off, and vice versa.

### 4.5 Ranking / structure

- **Kendall's τ** for group standings.
- **Bracket score** with round weights `1, 2, 4, 8, 16` for R16, QF, SF, F, Champion.
- **nDCG@3** for top-scorer predictions.

## 5. Settings (S1, S2)

Two settings, one per family of model:

- **S1** — plain LLM with the full context pack injected into the prompt: official 23-man squads, recent form (last ~10 matches per side), up to 20 pre-match news headlines from trusted sources, and recent stats aggregates. Tools off. Measures what an LLM can do when given the same evidence a human analyst would assemble.
- **S2** — search-enabled LLM or deep-research agent with tools on. The prompt tells the model what kinds of evidence to gather (squads / form / news / stats), shows one short worked example of each (drawn from the fixture's `context_pack` when available), and explicitly invites it to pull any additional evidence it thinks would sharpen the forecast. No context is pre-injected. Measures what a tool-using model/agent can do on its own.

The **Research Uplift** is defined as S2 − S1 for comparable model pairs (same base model in both its LLM and tool-using variants, e.g. Claude Sonnet vs Claude Sonnet + web_search). Earlier drafts of this report also had "no info, no tools" and "tools, no prompt guidance" cells; both were dropped because they answered questions we are not trying to measure (pure prior / unprompted retrieval).

## 6. Probability elicitation

All models are asked to return distributions, not point predictions. This is load-bearing:

1. Brier/RPS **separates well-calibrated uncertainty** from lucky guesses.
2. It aligns with bookmaker odds baseline (odds are implicitly probabilities).
3. It prevents the "always predict 1-0" degenerate strategy from scoring well under exact-match.

We normalise distributions post-hoc if the model returns unnormalised probabilities, but apply a small penalty (5 %) if the sum is off by > 1e-3.

## 7. Leakage audit

Agents with web search can trivially read post-kickoff reports and "predict" what already happened. We mitigate as follows:

- Every response must include `sources[]` with `url` and `accessed_at`.
- Before kickoff we record `lock_at_utc = kickoff − 1h`.
- Post-grading, an audit job fetches each source URL's publication metadata. Any source with `published_at > lock_at_utc` invalidates the dependent task (0 score). The leaderboard flags models with any leakage events.

We considered also running a "date-constrained" search tool, but most provider APIs don't expose deterministic pre-lock filtering, so post-hoc audit is the pragmatic fallback.

## 8. Baselines

- **Bookmaker (Pinnacle closing, devigged)**: industry-standard calibrated forecaster. Models beating Pinnacle across a season are non-trivial.
- **FiveThirtyEight SPI / club SPI**: statistical model, publicly available until project sunset; we snapshot until the benchmark ends.
- **Chalk**: always pick the higher-ranked team, score 1-0. Useful floor.

## 9. Phase 1 — UCL 2025-26 (planned)

- SF1 L1, SF1 L2, SF2 L1, SF2 L2, Final = 5 matches.
- Pre-SF tournament-level prediction once, then update after each leg.
- Expected ~$155 API spend. Results populate this section.

## 10. Phase 2 — World Cup 2026 (planned)

- 64 matches, group + knockout.
- Pre-tournament prediction on 2026-06-10.
- Per-match T-1h predictions.
- Post-round re-prediction of remaining knockouts.
- Expected ~$1,928 API spend.

## 11. Threats to validity

- **Popular fixtures bias**: LLMs will know more about Real Madrid than Auckland City. We partially control by also reporting **relative** gains (S2 vs S1 on a same-base-model pair).
- **Bookmaker as baseline**: Pinnacle closing odds incorporate market-aggregate information — beating them consistently is very hard. We report "Above-Market" as a separate, harder-to-beat leaderboard.
- **Prompt sensitivity**: small prompt changes can swing scores by several points. We fix the prompt templates in `prompts/` and report the exact SHA of the prompt file alongside each run.
- **Model-version drift**: vendors silently update models. We record model version strings and API response metadata to be able to flag this.

## 12. Reproducibility

- All code open-source under MIT.
- All predictions (`data/predictions/`) committed, together with `fixture.snapshot_hash`.
- Grading is deterministic given prediction + truth; rerunning `src.pipeline.orchestrator grade` reproduces scores.
