# Per-match prediction task template
#
# Variables rendered by src/pipeline/prompt_build.py:
#   fixture_header      always present
#   tie_context_block   always present when inferred / provided
#   squads_block        only if setting.inject.squads          (S1)
#   recent_form_block   only if setting.inject.recent_form     (S1)
#   news_block          only if setting.inject.news_headlines  (S1)
#   stats_block         only if setting.inject.stats           (S1)
#   search_guidance_block  only if setting.inject.search_guidance  (S2)
#   schema              JSON schema (compacted)

## Fixture

{{fixture_header}}

{{tie_context_block}}

{{squads_block}}

{{recent_form_block}}

{{news_block}}

{{stats_block}}

{{search_guidance_block}}

## Task

Predict the outcome of this match. Produce a single JSON object conforming **exactly** to the JSON Schema below.

```json
{{schema}}
```

### Field guide (all listed fields are required unless marked optional)

1. `reasoning`  — **emit this first**
   - `reasoning.overall`   main rationale, ≥ 80 chars
   - `reasoning.t1_result` / `t2_player` / `t3_events` / `t4_stats`  per-layer rationale
2. `score_dist` — **at least 10** distinct scorelines, sum ≈ 1. Must include: `0-0`, `1-1`, at least one away win with ≥ 2 away goals, and at least one result with ≥ 3 total goals. Derive each probability from xG estimates — do NOT default to `1-0 / 2-0 / 2-1`. Predict **full-time score only** (90 min regulation, or 120 min if extra time is played in a knockout); penalty shootouts are excluded. Do **not** output `win_probs` or `most_likely_score`; the system derives both from this distribution.
3. `expected_goal_diff`  home minus away (can be negative); keep it consistent with your scoreline distribution
4. `match_profile`  one of `low_event`, `normal`, `open`, `chaos`; choose before exact scorelines
5. `expected_total_goals`  expected match total goals; estimate this BEFORE exact scorelines and keep it consistent with `score_dist`
6. `over_under_probs`  `{over_1_5, over_2_5, over_3_5, over_4_5}`; monotonic and consistent with `expected_total_goals`
7. `advance_prob`  (optional; knockout legs only) probability the `home` team advances on aggregate
8. `lineups` { home, away } each with `starting` (exactly 11) and `bench`
9. `formations` { home, away }
10. `scorers`  every predicted scorer with `player`, `team`, `minute_range`, `p`
11. `assisters` (optional) similar shape, no minutes
12. `substitutions` (optional) `{team, off, on, minute}`
13. `cards` (optional) `{player, team, color, minute}`
14. `penalties` (optional) `{team, taker, outcome, minute}`
15. `own_goals` (optional) `{player, team, minute}`
16. `motm_probs` (optional) MOTM candidates with probability
17. `stats`  all 8 required keys, each `{home, away}`
18. `sources` (optional)  if you used retrieval, list every URL with `accessed_at`

Before filling `score_dist`, choose `match_profile`.
For two-leg knockout ties, explicitly use the previous-leg score and aggregate game state:
if the first leg had 6+ total goals, both teams' recent games are high-scoring, or one side
must chase, do not let a generic low-score football prior dominate. High-event draws such as
`2-2` / `3-3` and home/away wins such as `3-2` / `2-3` must receive realistic probability mass
when supported by the evidence.

### Setting

Setting for this run: **{{setting_id}}** — {{setting_description}}

Return JSON only. Begin with `{`.
