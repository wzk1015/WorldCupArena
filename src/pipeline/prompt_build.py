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


def _render_search_guidance(fixture: dict[str, Any], ctx: dict[str, Any]) -> str:
    """Block used by S2 (tools-on) to tell the model what kinds of evidence to
    gather and show one short concrete example of each, drawn from the fixture's
    context_pack when available. The model is free to search for more.
    """
    home = fixture["home"]["name"]
    away = fixture["away"]["name"]

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

    return (
        f"### Self-directed research (tools enabled)\n"
        f"You have web-search / browsing tools available. Before predicting, "
        f"search for up-to-date evidence about **{home} vs {away}**. "
        f"Work through the factor checklist in the system prompt — squad quality, "
        f"recent form, head-to-head, tactics, formation matchup, player chemistry, "
        f"individual matchups, injuries/suspensions, stakes, fixture congestion, "
        f"weather, referee, bookmaker signals — and gather evidence for the ones "
        f"that materially move the forecast.\n"
        f"\n"
        f"At minimum, collect the four core signals below:\n"
        f"\n"
        f"1. **Official 23-man squads** for both sides, with position / age / club. {_example_squad()}.\n"
        f"2. **Recent form** — last ~10 matches per side (date, competition, opponent, result, score). {_example_form()}.\n"
        f"3. **Pre-match news headlines** — aim for ~{NEWS_HEADLINE_CAP} trusted-source items "
        f"covering injuries, suspensions, press-conference notes, tactical previews, and predicted lineups. {_example_news()}.\n"
        f"4. **Recent stats** — rolling per-team aggregates (xG, shots, possession, pass accuracy, "
        f"defensive actions) over a comparable window. {_example_stats()}.\n"
        f"\n"
        f"Then, whenever it sharpens the forecast, also pull: **head-to-head record** "
        f"(including venue splits), **key individual matchups** (e.g. their winger "
        f"vs your full-back), **set-piece specialists and takers**, **referee profile** "
        f"(cards/penalties per game), **weather forecast** for kickoff, and **closing "
        f"bookmaker odds** as a market-prior cross-check.\n"
        f"\n"
        f"Record every URL you actually used under the prediction's `sources[]` "
        f"with an ISO-8601 `accessed_at`. Any source published *after* "
        f"`{fixture.get('lock_at_utc','<lock_at_utc>')}` will zero out the "
        f"tasks it influenced, so filter by date as you go.\n"
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
