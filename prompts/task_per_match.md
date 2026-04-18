# Per-match prediction task template
#
# Variables rendered by src/pipeline/prompt_build.py:
#   {{fixture_header}}      always present
#   {{squads_block}}        only if setting.inject.squads          (S1)
#   {{recent_form_block}}   only if setting.inject.recent_form     (S1)
#   {{news_block}}          only if setting.inject.news_headlines  (S1)
#   {{stats_block}}         only if setting.inject.stats           (S1)
#   {{search_guidance_block}}  only if setting.inject.search_guidance  (S2)
#   {{schema}}              JSON schema (compacted)

## Fixture

{{fixture_header}}

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
2. `win_probs` { home, draw, away }, sum ≈ 1
3. `score_dist` top-5 to top-20 scorelines with probabilities (sum ≈ 1)
4. `most_likely_score`  "H-A"
5. `expected_goal_diff`  home minus away (can be negative)
6. `advance_prob`  (optional; knockout legs only) probability the `home` team advances on aggregate
7. `lineups` { home, away } each with `starting` (exactly 11) and `bench`
8. `formations` { home, away }
9. `scorers`  every predicted scorer with `player`, `team`, `minute_range`, `p`
10. `assisters` (optional) similar shape, no minutes
11. `substitutions` (optional) `{team, off, on, minute}`
12. `cards` (optional) `{player, team, color, minute}`
13. `penalties` (optional) `{team, taker, outcome, minute}`
14. `own_goals` (optional) `{player, team, minute}`
15. `motm_probs` (optional) MOTM candidates with probability
16. `stats`  all 8 required keys, each `{home, away}`
17. `sources` (optional)  if you used retrieval, list every URL with `accessed_at`

### Setting

Setting for this run: **{{setting_id}}** — {{setting_description}}

Return JSON only. Begin with `{`.
