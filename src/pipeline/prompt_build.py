"""Build final user prompts from a fixture snapshot + setting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"
SCHEMAS = ROOT / "schemas"


def _render_squads(squads: dict[str, Any]) -> str:
    if not squads:
        return ""
    lines = ["### Official squads"]
    for side in ("home", "away"):
        lines.append(f"**{side.title()}** ({squads.get(side, {}).get('team_name','?')}):")
        for p in squads.get(side, {}).get("players", []):
            lines.append(f"- {p.get('name')} · {p.get('position','?')} · age {p.get('age','?')} "
                         f"· {p.get('club','?')}")
    return "\n".join(lines)


def _render_form(form: dict[str, Any]) -> str:
    if not form:
        return ""
    lines = ["### Recent form (last 10)"]
    for side in ("home", "away"):
        lines.append(f"**{side.title()}**: {form.get(side, {}).get('summary','')}")
        for m in form.get(side, {}).get("matches", [])[:10]:
            lines.append(f"- {m.get('date')} {m.get('competition')} {m.get('opponent')} "
                         f"{m.get('result')} ({m.get('score')})")
    return "\n".join(lines)


NEWS_HEADLINE_CAP = 20  # how many pre-match headlines to inject / show as examples


def _render_news(news: list[dict[str, Any]]) -> str:
    if not news:
        return ""
    lines = [f"### Recent news headlines (pre-match, from trusted sources; up to {NEWS_HEADLINE_CAP})"]
    for n in news[:NEWS_HEADLINE_CAP]:
        lines.append(f"- [{n.get('published_at','?')}] {n.get('source','?')}: "
                     f"{n.get('title')} — {n.get('url','')}")
    return "\n".join(lines)


def _render_stats(stats: dict[str, Any]) -> str:
    if not stats:
        return ""
    return "### Recent stats\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=2) + "\n```"


def _parse_score(score: str) -> tuple[int, int] | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _norm_team(name: str) -> str:
    return " ".join(str(name or "").casefold().replace(".", " ").split())


def _get_tie_context(fixture: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Return explicit two-leg context, inferring it from recent form if needed."""
    existing = ctx.get("tie_context")
    if isinstance(existing, dict) and existing:
        return existing

    stage = str(fixture.get("stage", "")).casefold()
    knockout_hint = any(word in stage for word in ("semi", "quarter", "final", "round", "knockout", "play"))
    competition = str(fixture.get("competition", "")).casefold()
    two_leg_comp_hint = any(
        name in competition
        for name in ("champions league", "europa league", "conference league", "libertadores", "sudamericana")
    )
    if not knockout_hint or not two_leg_comp_hint:
        return None

    form = ctx.get("recent_form") or {}
    home_matches = (form.get("home") or {}).get("matches") or []
    away_matches = (form.get("away") or {}).get("matches") or []
    home_name = fixture["home"]["name"]
    away_name = fixture["away"]["name"]
    away_norm = _norm_team(away_name)

    previous = None
    for match in home_matches:
        if _norm_team(match.get("opponent", "")) != away_norm:
            continue
        parsed = _parse_score(match.get("score", ""))
        if not parsed:
            continue
        current_home_goals, current_away_goals = parsed
        if str(match.get("venue", "")).upper() == "H":
            previous_home = home_name
            previous_away = away_name
            previous_score = f"{current_home_goals}-{current_away_goals}"
        else:
            previous_home = away_name
            previous_away = home_name
            previous_score = f"{current_away_goals}-{current_home_goals}"
        previous = {
            "date": match.get("date"),
            "competition": match.get("competition"),
            "home": previous_home,
            "away": previous_away,
            "score": previous_score,
            "current_home_goals": current_home_goals,
            "current_away_goals": current_away_goals,
            "total_goals": current_home_goals + current_away_goals,
        }
        break

    if previous is None:
        return None

    recent_totals = []
    for match in [*home_matches[:10], *away_matches[:10]]:
        parsed = _parse_score(match.get("score", ""))
        if parsed:
            recent_totals.append(parsed[0] + parsed[1])
    recent_avg_total = round(sum(recent_totals) / len(recent_totals), 2) if recent_totals else None

    home_agg = previous["current_home_goals"]
    away_agg = previous["current_away_goals"]
    margin = abs(home_agg - away_agg)
    leader = "level" if home_agg == away_agg else "home" if home_agg > away_agg else "away"
    if leader == "home":
        home_state = f"{home_name} lead by {margin}; they can manage phases but should not assume a low-event match."
        away_state = f"{away_name} trail by {margin}; they must chase if the game state stays unchanged."
    elif leader == "away":
        home_state = f"{home_name} trail by {margin}; a one-goal win forces extra time, a two-goal win advances in regulation."
        away_state = f"{away_name} lead by {margin}; a draw advances, but protecting the lead can invite pressure and transition chances."
    else:
        home_state = f"The tie is level; one goal can radically change both teams' risk appetite."
        away_state = home_state

    return {
        "kind": "two_leg_knockout",
        "inferred": True,
        "previous_leg": previous,
        "aggregate": {"home": home_agg, "away": away_agg, "leader": leader, "margin": margin},
        "away_goals_rule": "not_used_assumed",
        "home_game_state": home_state,
        "away_game_state": away_state,
        "recent_avg_total_goals": recent_avg_total,
    }


def _render_tie_context(fixture: dict[str, Any], ctx: dict[str, Any]) -> str:
    tie = _get_tie_context(fixture, ctx)
    if not tie:
        return ""

    previous = tie.get("previous_leg") or {}
    aggregate = tie.get("aggregate") or {}
    lines = ["### Two-leg / aggregate context"]
    if previous:
        lines.append(
            f"- Previous leg: {previous.get('date','?')} {previous.get('home','?')} "
            f"{previous.get('score','?')} {previous.get('away','?')} "
            f"({previous.get('total_goals','?')} total goals)."
        )
    if aggregate:
        lines.append(
            f"- Aggregate before kickoff from this fixture's home/away perspective: "
            f"home {aggregate.get('home','?')} - away {aggregate.get('away','?')} "
            f"(leader={aggregate.get('leader','?')}, margin={aggregate.get('margin','?')})."
        )
    if tie.get("away_goals_rule"):
        lines.append(f"- Away-goals rule: {tie.get('away_goals_rule')}.")
    if tie.get("home_game_state"):
        lines.append(f"- Home game state: {tie.get('home_game_state')}")
    if tie.get("away_game_state"):
        lines.append(f"- Away game state: {tie.get('away_game_state')}")
    if tie.get("recent_avg_total_goals") is not None:
        lines.append(f"- Recent combined total-goals average across both teams' listed form: {tie.get('recent_avg_total_goals')}.")
    lines.append(
        "- Use this context explicitly when estimating expected_total_goals, "
        "over_3_5 / over_4_5, score_dist, and advance_prob."
    )
    return "\n".join(lines)


def _render_search_guidance(fixture: dict[str, Any], ctx: dict[str, Any]) -> str:
    """Block used by S2 (tools-on) to tell the model what kinds of evidence to
    gather and show one short concrete example of each, drawn from the fixture's
    context_pack when available. The model is free to search for more.
    """
    home = fixture["home"]["name"]
    away = fixture["away"]["name"]
    tie = _get_tie_context(fixture, ctx)

    def _example_squad() -> str:
        squads = ctx.get("squads") or {}
        for side in ("home", "away"):
            players = (squads.get(side) or {}).get("players") or []
            if players:
                p = players[0]
                team = (squads.get(side) or {}).get("team_name", side)
                return (f"e.g. `{p.get('name','?')} · {p.get('position','?')} · "
                        f"age {p.get('age','?')} · {p.get('club','?')}` (from {team})")
        return f"e.g. `Harry Kane · ST · age 32 · Bayern Munich`"

    def _example_form() -> str:
        form = ctx.get("recent_form") or {}
        for side in ("home", "away"):
            matches = (form.get(side) or {}).get("matches") or []
            if matches:
                m = matches[0]
                return (f"e.g. `{m.get('date','YYYY-MM-DD')} {m.get('competition','?')} "
                        f"{m.get('opponent','?')} {m.get('result','?')} ({m.get('score','?')})`")
        return "e.g. `2026-04-09 UCL Real Madrid W (2-1)`"

    def _example_news() -> str:
        news = ctx.get("news_headlines") or []
        if news:
            n = news[0]
            return (f"e.g. `[{n.get('published_at','?')}] {n.get('source','?')}: "
                    f"{n.get('title','?')}`")
        return "e.g. `[2026-04-15] BBC Sport: Bayern confirm Neuer fit for semi`"

    def _example_stats() -> str:
        stats = ctx.get("stats_last_n") or {}
        if stats:
            first_key = next(iter(stats.keys()))
            return f"e.g. `{first_key}: {stats[first_key]!r}`"
        return "e.g. `xG last 5: {home: 1.8, away: 1.4}`"

    tie_guidance = (
        f"\nFor this two-leg tie, verify the previous-leg score, aggregate state, "
        f"away-goals rule, and each team's must-chase / can-protect incentives before "
        f"estimating total goals.\n"
        if tie else
        f"\nIf your searches show this is part of a two-leg tie, explicitly collect the "
        f"previous-leg score, aggregate state, away-goals rule, and game-state incentives.\n"
    )

    return (
        f"### Self-directed research (tools enabled) — MANDATORY\n"
        f"**You MUST actively use your web-search / browsing tools before making any prediction.** "
        f"Do NOT rely solely on training-data knowledge — it is outdated and insufficient for a "
        f"match-level forecast. Performing zero or token searches will be treated as a protocol "
        f"violation and will severely penalise your score.\n"
        f"\n"
        f"**Required minimum**: issue **at least 6 distinct search queries** covering the four "
        f"core signals below before writing any JSON. Think step-by-step: search → read → search "
        f"again with what you learned → then predict.\n"
        f"\n"
        f"Work through the factor checklist in the system prompt — squad quality, "
        f"recent form, head-to-head, tactics, formation matchup, player chemistry, "
        f"individual matchups, injuries/suspensions, stakes, fixture congestion, "
        f"weather, referee, bookmaker signals — and gather evidence for the ones "
        f"that materially move the forecast.\n"
        f"\n"
        f"**Four core signals you MUST collect** (search for each before predicting):\n"
        f"\n"
        f"1. **Official 23-man squads** for both {home} and {away}, with position / age / club. {_example_squad()}.\n"
        f"2. **Recent form** — last ~10 matches per side (date, competition, opponent, result, score). {_example_form()}.\n"
        f"3. **Pre-match news headlines** — aim for ~{NEWS_HEADLINE_CAP} trusted-source items "
        f"covering injuries, suspensions, press-conference notes, tactical previews, and predicted lineups. {_example_news()}.\n"
        f"4. **Recent stats** — rolling per-team aggregates (xG, shots, possession, pass accuracy, "
        f"defensive actions) over a comparable window. {_example_stats()}.\n"
        f"\n"
        f"**Additional signals to search for** (pull whenever they sharpen the forecast): "
        f"**head-to-head record** (including venue splits), **key individual matchups** "
        f"(e.g. their winger vs your full-back), **set-piece specialists and takers**, "
        f"**referee profile** (cards/penalties per game), **weather forecast** for kickoff, "
        f"and **closing bookmaker odds** as a market-prior cross-check.\n"
        f"{tie_guidance}"
        f"\n"
        f"Record every URL you actually visited under the prediction's `sources[]` "
        f"with an ISO-8601 `accessed_at`. Any source published *after* "
        f"`{fixture.get('lock_at_utc','<lock_at_utc>')}` will zero out the "
        f"tasks it influenced, so filter by date as you go.\n"
        f"\n"
        f"**Do not start writing the JSON until you have completed your research.**\n"
    )


def _render_fixture_header(fixture: dict[str, Any]) -> str:
    return (
        f"### Fixture\n"
        f"- Competition: {fixture.get('competition')}\n"
        f"- Stage: {fixture.get('stage')}\n"
        f"- Kickoff (UTC): {fixture.get('kickoff_utc')}\n"
        f"- Home: {fixture['home']['name']} (id={fixture['home']['id']})\n"
        f"- Away: {fixture['away']['name']} (id={fixture['away']['id']})\n"
        f"- Venue: {fixture.get('venue','?')}\n"
        f"- Fixture id: {fixture['fixture_id']}\n"
        f"- Prediction lock at (UTC): {fixture['lock_at_utc']}\n"
    )


def build_prompt(
    fixture: dict[str, Any],
    setting: dict[str, Any],
    template_name: str = "task_per_match.md",
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt)."""
    system = (PROMPTS / "system.md").read_text()
    tpl = (PROMPTS / template_name).read_text()
    schema = json.loads((SCHEMAS / "prediction.schema.json").read_text())

    inject = setting.get("inject", {})
    ctx = fixture.get("context_pack", {})

    user = (
        tpl.replace("{{fixture_header}}", _render_fixture_header(fixture))
           .replace("{{tie_context_block}}", _render_tie_context(fixture, ctx))
           .replace("{{squads_block}}", _render_squads(ctx.get("squads", {})) if inject.get("squads") else "")
           .replace("{{recent_form_block}}", _render_form(ctx.get("recent_form", {})) if inject.get("recent_form") else "")
           .replace("{{news_block}}", _render_news(ctx.get("news_headlines", [])) if inject.get("news_headlines") else "")
           .replace("{{stats_block}}", _render_stats(ctx.get("stats_last_n", {})) if inject.get("stats") else "")
           .replace("{{search_guidance_block}}",
                    _render_search_guidance(fixture, ctx) if inject.get("search_guidance") else "")
           .replace("{{schema}}", json.dumps(schema))
           .replace("{{setting_id}}", setting["id"])
           .replace("{{setting_description}}", setting.get("description", ""))
    )
    return system, user
