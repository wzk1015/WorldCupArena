# Per-match prediction task template
#
# Variables rendered by src/pipeline/prompt_build.py:
#   {{fixture_header}}   always present
#   {{squads_block}}     only if setting.inject.squads
#   {{recent_form_block}}  only if setting.inject.recent_form
#   {{news_block}}       only if setting.inject.news_headlines
#   {{stats_block}}      only if setting.inject.stats
#   {{schema}}           JSON schema (compacted)

## Fixture

{{fixture_header}}

{{squads_block}}

{{recent_form_block}}

{{news_block}}

{{stats_block}}

## Task

Predict the outcome of this match. Produce a single JSON object conforming exactly to this JSON Schema:

```json
{{schema}}
```

Required fields for this task:
- `win_probs` (home/draw/away, normalized)
- `score_dist` (top-5 scorelines with probabilities; include an "other" bucket if needed)
- `most_likely_score`
- `expected_goal_diff` (home minus away)
- `lineups` (best-effort starting XI for each side)
- `formations`
- `scorers` (predicted scorers with probability and minute_range)
- `stats` (possession, shots, shots_on_target, corners, pass_accuracy, fouls, saves, defensive_actions for each side)
- `cards`, `substitutions`: best-effort; empty array allowed if highly uncertain
- `reasoning`: concise rationale
- `sources`: if you used any external retrieval

Setting for this run: **{{setting_id}}** — {{setting_description}}

Return JSON only.
