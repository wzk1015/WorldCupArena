# Introducing WorldCupArena

**Can GPT-5, Claude Opus 4.7, or MiroThinker H1 pick this week's Champions League semi-final?**

WorldCupArena is a new public benchmark that puts frontier LLMs and deep-research agents against real, future football matches — starting with the UEFA Champions League 2025-26 semi-finals in late April, and scaling up to the full 2026 FIFA World Cup this June.

## The task

For every match, models must predict — **before kickoff** — a rich, probabilistic JSON covering:

- Win / draw / loss probabilities and scoreline distribution
- Starting XIs and formations
- Goalscorers (with probability and expected minute range)
- Substitutions, cards, penalties, own goals
- Match statistics: possession, shots, corners, pass accuracy, defensive actions
- For the tournament level: group standings, bracket, champion, top scorer

## Why this is hard for models

Football is the tightest possible test for a deep-research agent:

1. **The answer changes daily.** Injury news at 10 a.m. can flip the score line at 8 p.m.
2. **Sources disagree.** Official club statements, reputable journalism, odds markets, and Twitter rumours can each point different directions.
3. **Ground truth is abundant.** One 90-minute match yields dozens of gradable signals — an F1 on goalscorers, a Hungarian-matched MAE on minutes, a sMAPE on corners.
4. **Leakage is trivially punishable.** Every source link is audited against kickoff-minus-24h; any article published after lock disqualifies the task.

## How we score

- **Brier / RPS** for probability fields (not accuracy — that rewards lucky guesses).
- **Hungarian assignment** on time-stamped events (goals, subs, cards).
- **Jaccard + position** for lineups. **Bracket score** for knockouts.
- Composite 0–100 per (model, setting). Three leaderboards: main, above-market (vs. Pinnacle closing), and **Research Uplift** (S2 − S1, i.e. tool-using self-search vs the same model family fed a curated context pack).

## Who's competing

Closed: GPT-5, Claude Opus 4.7 / Sonnet 4.6, Gemini 2.5 Pro/Flash, Grok 4.
Open: DeepSeek V3.2 / R1, Qwen3-Max, Llama-4 Maverick.
Deep-research agents: OpenAI Deep Research, Gemini Deep Research, Perplexity Deep Research, Claude Research, MiroMind's **MiroThinker 1.7 / H1**.
Baselines: Pinnacle closing odds, 538 SPI, naive chalk.

Contributions welcome — wiring up a new model is one file in `src/runners/`.

## Timeline

- **Now**: Phase 0 dry-run (Premier League fixture).
- **2026-04-28 → 05-06**: UCL semi-final first/second legs.
- **2026-05-30**: UCL final.
- **2026-06-10**: Pre-tournament full World Cup prediction goes live.
- **2026-06-11 → 07-19**: 64 matches, round-by-round re-prediction.
- **2026-08**: Final write-up + technical report.

Follow progress at `docs/leaderboard/`. PRs at [github.com/…/WorldCupArena].
