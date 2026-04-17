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


def _render_news(news: list[dict[str, Any]]) -> str:
    if not news:
        return ""
    lines = ["### Recent news headlines (pre-match, from trusted sources)"]
    for n in news[:30]:
        lines.append(f"- [{n.get('published_at','?')}] {n.get('source','?')}: "
                     f"{n.get('title')} — {n.get('url','')}")
    return "\n".join(lines)


def _render_stats(stats: dict[str, Any]) -> str:
    if not stats:
        return ""
    return "### Recent stats\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=2) + "\n```"


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
           .replace("{{schema}}", json.dumps(schema))
           .replace("{{setting_id}}", setting["id"])
           .replace("{{setting_description}}", setting.get("description", ""))
    )
    return system, user
