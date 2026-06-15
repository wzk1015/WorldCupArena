# Per-match prediction task template
#
# Variables rendered by src/pipeline/prompt_build.py:
#   fixture_header      always present
#   tie_context_block   always present when inferred / provided
#   squads_block        only if setting.inject.squads          (S1)
#   recent_form_block   only if setting.inject.recent_form     (S1)
#   news_block          only if setting.inject.news_headlines  (S1)
#   stats_block         only if setting.inject.stats           (S1)
#   odds_block          only if setting.inject.odds            (S1)
#   search_guidance_block  only if setting.inject.search_guidance  (S2)
#   schema              JSON schema (compacted)

## Fixture

{{fixture_header}}

{{tie_context_block}}

{{squads_block}}

{{recent_form_block}}

{{news_block}}

{{stats_block}}

{{odds_block}}

{{search_guidance_block}}

## Task

Predict the outcome of this match. Produce a single JSON object conforming **exactly** to the JSON Schema below.

Write all explanatory/narrative text in Simplified Chinese. Keep structured scoring fields machine-stable: official/API player names in player-name fields, exact schema enum values, `H-A` score strings, and numeric probabilities/statistics. If useful, mention Chinese or bilingual player names inside the Chinese reasoning text, not in structured player-name fields.

This benchmark now evaluates the model's own final result and final score point forecast. Do **not** output per-score probabilities. The system may still generate legacy display fields after your response, but your required score forecast is `headline_score` and your required result forecast is `predicted_result`.

```json
{{schema}}
```

### Field guide (all listed fields are required unless marked optional)

1. `reasoning`  — **emit this first** and fill every required subfield with real analysis, not placeholders.
   - `overall`  synthesis across market, squad quality, form, tactics, player availability, matchup paths, and final-score logic.
   - `market_odds`  bookmaker/implied-probability read and where you agree or disagree.
   - `lineup_analysis`  expected starting XIs, role balance, bench/rotation logic.
   - `tactical_analysis`  pressing, buildup, transitions, set pieces, width/centrality, match tempo.
   - `h2h_recent_form`  head-to-head, recent results, goals/xG trend, venue/travel/context.
   - `player_matchups`  concrete duels: winger vs full-back, striker vs centre-backs, midfield pressure, set-piece targets.
   - `injuries_availability`  injuries, suspensions, fitness doubts, late rotation risk; say when evidence is thin.
   - `upset_draw_blowout_cases`  explicitly argue plausible draw/upset/blowout paths before choosing.
   - `score_result_rationale`  why `predicted_result`, `headline_score`, `win_probs`, total goals, and goal diff cohere.
   - `t1_result` / `t2_player` / `t3_events` / `t4_stats`  per-layer rationale.
2. `predicted_result` one of `home`, `draw`, `away`; this is your final result pick and must match both the `headline_score` result and the highest `win_probs` bucket.
3. `headline_score` one exact full-time score `"H-A"`; this is your final score pick. It is evaluated directly.
4. `win_probs` `{home, draw, away}`, sum ≈ 1. Estimate from evidence plus market prior, but do not let odds force a conservative pick.
5. `match_profile`  one of `low_event`, `normal`, `open`, `chaos`; choose before the score.
6. `expected_total_goals`  expected match total goals; keep it consistent with the profile and score.
7. `expected_goal_diff`  home minus away (can be negative); keep it consistent with result and score.
8. `advance_prob`  (optional; knockout legs only) probability the `home` team advances on aggregate.
9. `lineups` { home, away } each with `starting` (exactly 11) and `bench`.
10. `formations` { home, away }.
11. `scorers`  predicted scoring candidates/events with `player`, `team`, `minute_range`, `p`. For high scores, include enough plausible scorers to support the score story.
12. `assisters` (optional) `{player, team, p, minute?}`. When possible, set `minute` near the assisted goal so the timeline can attach the assist to the right scorer.
13. `substitutions` (optional) `{team, off, on, minute}`.
14. `cards` (optional) `{player, team, color, minute}`.
15. `penalties` (optional) `{team, taker, outcome, minute}`. A scored penalty counts as one goal for `team`.
16. `own_goals` (optional) `{player, team, minute}` where `team` is the player's own team; the goal is credited to the opposite side.
17. `key_events` (optional) `{team, minute, label, player?, type?}` for important non-goal/card/substitution events such as VAR review or injury stoppage. Do not duplicate goals, penalties, own goals, cards, or substitutions.
18. `motm_probs` (optional) MOTM candidates with probability.
19. `stats`  all 8 required keys, each `{home, away}`.
20. `sources` (optional)  if you used retrieval, list every URL with `accessed_at`.

Do **not** output `score_dist`, `most_likely_score`, or `over_under_probs`; the system generates them.
Before returning JSON, sanity-check the event timeline: if `headline_score` is `3-0`, the likely goal timeline should contain three credited home goals and zero credited away goals after counting scored penalties and own goals.
You are allowed to make an aggressive point forecast when the scenario is coherent. A heavy favorite can win `4-0`, `5-1`, `6-0`, or `7-1`; a live underdog can win; a tactically balanced match can have draw as the highest-probability result. Avoid defaulting every favorite to `1-0`, `2-0`, or `2-1`.
For two-leg knockout ties, explicitly use the previous-leg score and aggregate game state:
if the first leg had 6+ total goals, both teams' recent games are high-scoring, or one side
must chase, do not let a generic low-score football prior dominate. High-event headline scores
such as `2-2` / `3-3`, `3-2`, or `2-3` are appropriate when supported by the evidence and
their result matches your highest win-probability bucket.

### Setting

Setting for this run: **{{setting_id}}** — {{setting_description}}

Return JSON only. Begin with `{`.
