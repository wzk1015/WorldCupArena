# Full-tournament prediction task template (T5 tasks)

## Tournament

{{tournament_header}}

{{groups_block}}

{{team_info_block}}

{{news_block}}

## Task

Predict the entire tournament outcome. JSON object with fields:

- `group_standings`: per group, ordered team list with projected points/GF/GA.
- `bracket`: knockout bracket — at each slot specify the team you expect to advance and `p` (probability).
- `champion_probs`: map team_id -> probability, normalized over all teams.
- `top_scorer_probs`: top-10 player list with probabilities (normalized over the 10).
- `awards`: best GK ("golden glove"), best young player, MVP — each as `{name, team, p}`.
- `reasoning`: concise rationale covering dark horses / favorites / key injuries.
- `sources`: if retrieval was used.

Setting for this run: **{{setting_id}}**

Return JSON only.
