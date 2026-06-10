"""Tournament-level prediction runner for the 2026 World Cup.

This module is intentionally separate from the fixture scheduler. It asks each
selected model for a full tournament path, computes the group tables from the
model's group-stage scorelines, resolves the first knockout round, then asks the
same model to continue through the knockout bracket.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from ..runners import build_runner


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
MODELS_YAML = CONFIGS / "models.yaml"
SPEC_PATH = CONFIGS / "world_cup_2026_tournament.json"
CONTEXT_PACK = DATA / "tournament_context" / "world_cup_2026" / "context_pack.md"
OUT_DIR = DATA / "tournament_predictions" / "world_cup_2026"

SEARCH_CATEGORIES = {"search_llm", "deep_research_agent"}
GROUP_SETTING = {"id": "S1"}
SEARCH_SETTING = {"id": "S2"}

load_dotenv(ROOT / ".env")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_models() -> dict[str, dict[str, Any]]:
    cfg = yaml.safe_load(MODELS_YAML.read_text()) or {}
    models: dict[str, dict[str, Any]] = {}
    for category, rows in cfg.items():
        if category == "baselines":
            continue
        for row in rows or []:
            model_id = row.get("id")
            if not model_id:
                continue
            models[model_id] = {"model_category": category, **row}
    return models


def _model_setting(model_cfg: dict[str, Any]) -> dict[str, str]:
    if model_cfg.get("model_category") in SEARCH_CATEGORIES:
        return SEARCH_SETTING
    for setting in model_cfg.get("settings_supported") or []:
        if setting == "S2":
            return SEARCH_SETTING
    return GROUP_SETTING


def _is_search_model(model_cfg: dict[str, Any]) -> bool:
    return _model_setting(model_cfg)["id"] == "S2"


def _runtime_model_cfg(model_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(model_cfg)
    cfg.setdefault("timeout_seconds", 600)
    cfg["timeout_seconds"] = max(int(cfg.get("timeout_seconds") or 0), 600)
    cfg.setdefault("max_tokens", 24000)
    return cfg


def _team_catalog(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for teams in (spec.get("groups") or {}).values():
        for team in teams:
            item = dict(team)
            out[item["name"]] = item
            out[item["id"]] = item
    return out


def _team_ref(team_name: str, spec: dict[str, Any], group: str | None = None, rank: int | None = None) -> dict[str, Any]:
    catalog = _team_catalog(spec)
    team = dict(catalog.get(team_name) or {"name": team_name, "id": _slug(team_name), "flag": "", "group": group})
    if group:
        team["group"] = group
    if rank is not None:
        team["rank"] = rank
    return {
        "id": team.get("id") or _slug(team.get("name")),
        "name": team.get("name") or team_name,
        "flag": team.get("flag") or "",
        "group": team.get("group") or group,
        "rank": team.get("rank", rank),
    }


def _slug(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-").lower() or "team"


def _score_tuple(value: Any) -> tuple[int, int] | None:
    match = re.search(r"(\d{1,2})\s*[-:–]\s*(\d{1,2})", str(value or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _score_string(value: Any) -> str | None:
    score = _score_tuple(value)
    if not score:
        return None
    return f"{score[0]}-{score[1]}"


def _result_from_score(score: str | None) -> str | None:
    parsed = _score_tuple(score)
    if not parsed:
        return None
    home, away = parsed
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def _side_from_value(value: Any, home: str, away: str) -> str | None:
    text = str(value or "").strip().casefold()
    if text in {"home", "h", "主", "主队"}:
        return "home"
    if text in {"away", "a", "客", "客队"}:
        return "away"
    if text == str(home or "").strip().casefold():
        return "home"
    if text == str(away or "").strip().casefold():
        return "away"
    return None


def _normal_goal_minute(value: Any) -> int | None:
    try:
        minute = int(value)
    except (TypeError, ValueError):
        return None
    if minute < 1 or minute > 130:
        return None
    return minute


def _raw_scorers(raw: dict[str, Any]) -> list[Any]:
    return (
        raw.get("scorers")
        or raw.get("goal_scorers")
        or raw.get("goalscorers")
        or raw.get("goals")
        or []
    )


def _normalize_scorers(raw: dict[str, Any], home: str, away: str, score: str) -> list[dict[str, Any]]:
    target = _score_tuple(score) or (0, 0)
    by_side: dict[str, list[dict[str, Any]]] = {"home": [], "away": []}

    for item in _raw_scorers(raw):
        if isinstance(item, str):
            item = {"player": item}
        if not isinstance(item, dict):
            continue
        side = _side_from_value(item.get("team") or item.get("side"), home, away)
        if not side:
            player_team = str(item.get("team_name") or "").strip()
            side = _side_from_value(player_team, home, away)
        if not side:
            continue
        player = str(item.get("player") or item.get("name") or item.get("scorer") or "").strip()
        if not player:
            continue
        entry = {
            "player": player,
            "team": side,
        }
        minute = _normal_goal_minute(item.get("minute") or item.get("min"))
        if minute is not None:
            entry["minute"] = minute
        by_side[side].append(entry)

    scorers: list[dict[str, Any]] = []
    for side, needed in (("home", target[0]), ("away", target[1])):
        side_rows = by_side[side][:needed]
        while len(side_rows) < needed:
            side_rows.append({"player": "未指定", "team": side})
        scorers.extend(side_rows)
    return scorers


def _build_system_prompt() -> str:
    return (
        "You are WorldCupArena's tournament-level football prediction engine. "
        "Return only one valid JSON object with no markdown. "
        "Use Simplified Chinese for narrative fields, but keep schema keys, score strings, "
        "enum values, team names, and structured player names machine-stable. "
        "Do careful football reasoning internally, then provide concise Chinese rationales."
    )


def _group_prompt(spec: dict[str, Any], context_pack: str, model_cfg: dict[str, Any]) -> str:
    matches = spec.get("group_stage_matches") or []
    groups = spec.get("groups") or {}
    search = _is_search_model(model_cfg)
    context_section = (
        "This is an S2/search model. Before predicting, use your search tools to verify current squads, "
        "injuries, form, and relevant news. Do not rely only on priors. Include useful sources in `sources`."
        if search
        else "This is an S1/non-search model. Use the injected context pack below as your news and squad context.\n\n"
             f"Injected context pack:\n{context_pack}"
    )
    match_ids = [m["match_no"] for m in matches]
    return f"""
Predict ONLY the group stage of the 2026 FIFA World Cup.

{context_section}

Output requirements:
- Include every group-stage match number exactly once: {match_ids}.
- For each match predict result, exact score, and goalscorers only.
- Do not predict starting lineups, cards, substitutions, xG, possession, or other stats.
- `score` must be an `H-A` score from the listed home team's perspective.
- `result` must be `home`, `draw`, or `away` and must agree with the score.
- `scorers[].team` must be `home` or `away`; use common official/English player names in structured fields.
- Narrative `reasoning` fields should be concise Simplified Chinese.

Return this JSON shape:
{{
  "stage": "group_stage",
  "model_tournament_summary": "中文概述小组赛预测思路。",
  "group_matches": [
    {{
      "match_no": 1,
      "group": "A",
      "home": "Mexico",
      "away": "South Africa",
      "score": "1-1",
      "result": "draw",
      "scorers": [
        {{"team": "home", "player": "Player Name", "minute": 34}},
        {{"team": "away", "player": "Player Name", "minute": 76}}
      ],
      "reasoning": "中文一句话说明。"
    }}
  ],
  "sources": []
}}

Groups:
{json.dumps(groups, ensure_ascii=False)}

Group-stage schedule:
{json.dumps(matches, ensure_ascii=False)}
""".strip()


def _knockout_prompt(
    spec: dict[str, Any],
    context_pack: str,
    model_cfg: dict[str, Any],
    group_summary: dict[str, Any],
    r32_bracket: list[dict[str, Any]],
) -> str:
    search = _is_search_model(model_cfg)
    context_section = (
        "This is an S2/search model. You may use search again to verify current tournament previews, "
        "squad/injury news, and likely knockout strengths before completing the bracket."
        if search
        else "This is an S1/non-search model. Use the injected context pack below as your current news context.\n\n"
             f"Injected context pack:\n{context_pack}"
    )
    knockout_template = spec.get("knockout_matches") or []
    return f"""
Continue the SAME model prediction into the 2026 World Cup knockout stage.

{context_section}

The group tables below were computed from your own group-stage score predictions. Do not change them.
The Round of 32 bracket below has already been resolved from those tables. Do not change Round-of-32 teams.
For matches 89-104, propagate winners/losers from your own previous knockout picks.

Knockout output requirements:
- Include every match number 73 through 104 exactly once.
- Predict result, score, winner, and goalscorers only.
- `score` must be an `H-A` score from the listed home team's perspective. If the match is decided on penalties, keep the regulation/extra-time score level and set `decider` to `PEN`; `winner` must still name the winning team.
- `winner` must be the exact team name of the winner.
- `scorers[].team` must be `home` or `away`.
- Do not predict lineups, cards, substitutions, xG, possession, or other stats.

Return this JSON shape:
{{
  "stage": "knockout",
  "knockout_summary": "中文概述淘汰赛路径和冠军判断。",
  "knockout_matches": [
    {{
      "match_no": 73,
      "stage": "R32",
      "home": "Team A",
      "away": "Team B",
      "score": "2-1",
      "winner": "Team A",
      "decider": "REG",
      "scorers": [
        {{"team": "home", "player": "Player Name", "minute": 22}}
      ],
      "reasoning": "中文一句话说明。"
    }}
  ],
  "champion": "Team Name",
  "sources": []
}}

Computed group-stage summary:
{json.dumps(group_summary, ensure_ascii=False)}

Resolved Round-of-32 bracket:
{json.dumps(r32_bracket, ensure_ascii=False)}

Full knockout template:
{json.dumps(knockout_template, ensure_ascii=False)}
""".strip()


def _call_json(runner: Any, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    out = runner.generate(system_prompt, [{"role": "user", "content": user_prompt}])
    text = out.get("text") or ""
    parsed = runner.parse_json(text)
    input_tokens = int(out.get("input_tokens") or 0)
    output_tokens = int(out.get("output_tokens") or 0)
    meta = {
        "raw_text": text,
        "thinking_text": out.get("thinking"),
        "sources": out.get("sources") or [],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": int(out.get("tool_calls") or 0),
        "cost_usd": float(out.get("cost_usd", runner.price_tokens(input_tokens, output_tokens)) or 0.0),
    }
    model_sources = parsed.get("sources") if isinstance(parsed, dict) else []
    if isinstance(model_sources, list):
        for source in model_sources:
            if source not in meta["sources"]:
                meta["sources"].append(source)
    return parsed, meta


def _normalize_group_matches(parsed: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = parsed.get("group_matches") or parsed.get("matches") or []
    by_no: dict[int, dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        try:
            match_no = int(row.get("match_no") or row.get("match") or row.get("id"))
        except (TypeError, ValueError):
            continue
        by_no[match_no] = row

    normalized: list[dict[str, Any]] = []
    for fixture in spec.get("group_stage_matches") or []:
        match_no = int(fixture["match_no"])
        raw = by_no.get(match_no)
        if raw is None:
            raise ValueError(f"group-stage prediction missing match {match_no}")
        score = _score_string(raw.get("score") or raw.get("predicted_score") or raw.get("final_score"))
        if not score:
            raise ValueError(f"group-stage prediction has invalid score for match {match_no}")
        result = _result_from_score(score)
        normalized.append({
            "match_no": match_no,
            "id": fixture.get("id") or f"M{match_no}",
            "group": fixture.get("group"),
            "home": fixture.get("home"),
            "away": fixture.get("away"),
            "score": score,
            "result": result,
            "scorers": _normalize_scorers(raw, fixture.get("home"), fixture.get("away"), score),
            "reasoning": str(raw.get("reasoning") or raw.get("rationale") or "").strip(),
            "kickoff_utc": fixture.get("kickoff_utc"),
            "venue": fixture.get("venue"),
        })
    return normalized


def compute_group_standings(matches: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, dict[str, dict[str, Any]]] = {}
    for group, teams in (spec.get("groups") or {}).items():
        tables[group] = {}
        for team in teams:
            tables[group][team["name"]] = {
                "team": team["name"],
                "team_id": team["id"],
                "flag": team.get("flag") or "",
                "group": group,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "points": 0,
            }

    for match in matches:
        group = match["group"]
        home, away = match["home"], match["away"]
        score = _score_tuple(match["score"])
        if not score:
            continue
        hg, ag = score
        hrow = tables[group][home]
        arow = tables[group][away]
        for row, gf, ga in ((hrow, hg, ag), (arow, ag, hg)):
            row["played"] += 1
            row["goals_for"] += gf
            row["goals_against"] += ga
            row["goal_difference"] = row["goals_for"] - row["goals_against"]
        if hg > ag:
            hrow["wins"] += 1
            arow["losses"] += 1
            hrow["points"] += 3
        elif ag > hg:
            arow["wins"] += 1
            hrow["losses"] += 1
            arow["points"] += 3
        else:
            hrow["draws"] += 1
            arow["draws"] += 1
            hrow["points"] += 1
            arow["points"] += 1

    out: dict[str, list[dict[str, Any]]] = {}
    for group, rows in tables.items():
        ordered = sorted(
            rows.values(),
            key=lambda row: (-row["points"], -row["goal_difference"], -row["goals_for"], row["team"]),
        )
        for idx, row in enumerate(ordered, 1):
            row["rank"] = idx
        out[group] = ordered
    return out


def _third_place_qualifiers(standings: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    thirds = [rows[2] for rows in standings.values() if len(rows) >= 3]
    thirds.sort(key=lambda row: (-row["points"], -row["goal_difference"], -row["goals_for"], row["team"]))
    return [{**row, "third_place_rank": idx} for idx, row in enumerate(thirds[:8], 1)]


def _assign_third_place_slots(spec: dict[str, Any], qualifiers: list[dict[str, Any]]) -> dict[str, str]:
    q_by_group = {row["group"]: row for row in qualifiers}
    slots: list[dict[str, Any]] = []
    for match in spec.get("knockout_matches") or []:
        for side_key in ("home_slot", "away_slot"):
            slot = match.get(side_key) or []
            if slot and slot[0] == "best_third":
                allowed = list(slot[1] or [])
                slots.append({
                    "key": f"{match['match_no']}:{side_key}",
                    "match_no": match["match_no"],
                    "side_key": side_key,
                    "allowed": allowed,
                    "candidates": [g for g in allowed if g in q_by_group],
                })

    rank_index = {row["group"]: row.get("third_place_rank", 999) for row in qualifiers}
    slots.sort(key=lambda slot: (len(slot["candidates"]), slot["match_no"], slot["side_key"]))
    assignment: dict[str, str] = {}
    used: set[str] = set()

    def backtrack(index: int) -> bool:
        if index >= len(slots):
            return True
        slot = slots[index]
        for group in sorted(slot["candidates"], key=lambda g: rank_index.get(g, 999)):
            if group in used:
                continue
            used.add(group)
            assignment[slot["key"]] = group
            if backtrack(index + 1):
                return True
            assignment.pop(slot["key"], None)
            used.remove(group)
        return False

    if not backtrack(0):
        raise ValueError("could not assign best-third teams to Round-of-32 slots")
    return assignment


def _resolve_slot(
    slot: list[Any],
    *,
    match: dict[str, Any],
    side_key: str,
    standings: dict[str, list[dict[str, Any]]],
    third_assignment: dict[str, str],
    spec: dict[str, Any],
) -> dict[str, Any]:
    kind = slot[0]
    if kind == "group_winner":
        group = slot[1]
        row = standings[group][0]
        return _team_ref(row["team"], spec, group, 1)
    if kind == "group_runner_up":
        group = slot[1]
        row = standings[group][1]
        return _team_ref(row["team"], spec, group, 2)
    if kind == "best_third":
        group = third_assignment[f"{match['match_no']}:{side_key}"]
        row = standings[group][2]
        return _team_ref(row["team"], spec, group, 3)
    raise ValueError(f"unsupported slot kind: {kind}")


def build_round_of_32(
    spec: dict[str, Any],
    standings: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    qualifiers = _third_place_qualifiers(standings)
    assignment = _assign_third_place_slots(spec, qualifiers)
    rows: list[dict[str, Any]] = []
    for match in spec.get("knockout_matches") or []:
        if match.get("stage") != "R32":
            continue
        home = _resolve_slot(
            match["home_slot"],
            match=match,
            side_key="home_slot",
            standings=standings,
            third_assignment=assignment,
            spec=spec,
        )
        away = _resolve_slot(
            match["away_slot"],
            match=match,
            side_key="away_slot",
            standings=standings,
            third_assignment=assignment,
            spec=spec,
        )
        rows.append({
            "match_no": match["match_no"],
            "id": match["id"],
            "stage": match["stage"],
            "home": home,
            "away": away,
            "home_slot": match["home_slot"],
            "away_slot": match["away_slot"],
        })
    return rows, qualifiers, assignment


def _winner_side(raw: dict[str, Any], home: dict[str, Any], away: dict[str, Any], score: str) -> str:
    result = _result_from_score(score)
    if result in {"home", "away"}:
        return result
    text = str(raw.get("winner") or raw.get("winning_team") or "").strip()
    if text.casefold() == str(home.get("name")).casefold() or text.casefold() == "home":
        return "home"
    if text.casefold() == str(away.get("name")).casefold() or text.casefold() == "away":
        return "away"
    return "home"


def _slot_team(slot: list[Any], resolved: dict[int, dict[str, Any]]) -> dict[str, Any]:
    kind, match_no = slot[0], int(slot[1])
    prev = resolved[match_no]
    if kind == "winner":
        return prev["winner"]
    if kind == "loser":
        return prev["loser"]
    raise ValueError(f"unsupported knockout propagation slot: {slot}")


def _normalize_knockout_matches(
    parsed: dict[str, Any],
    spec: dict[str, Any],
    r32_bracket: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_rows = parsed.get("knockout_matches") or parsed.get("matches") or []
    by_no: dict[int, dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        try:
            match_no = int(row.get("match_no") or row.get("match") or row.get("id"))
        except (TypeError, ValueError):
            continue
        by_no[match_no] = row

    r32_by_no = {row["match_no"]: row for row in r32_bracket}
    resolved: dict[int, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    for template in spec.get("knockout_matches") or []:
        match_no = int(template["match_no"])
        raw = by_no.get(match_no)
        if raw is None:
            raise ValueError(f"knockout prediction missing match {match_no}")
        if template["stage"] == "R32":
            home = r32_by_no[match_no]["home"]
            away = r32_by_no[match_no]["away"]
        else:
            home = _slot_team(template["home_slot"], resolved)
            away = _slot_team(template["away_slot"], resolved)
        score = _score_string(raw.get("score") or raw.get("final_score"))
        if not score:
            raise ValueError(f"knockout prediction has invalid score for match {match_no}")
        side = _winner_side(raw, home, away, score)
        winner = home if side == "home" else away
        loser = away if side == "home" else home
        row = {
            "match_no": match_no,
            "id": template.get("id") or f"M{match_no}",
            "stage": template.get("stage"),
            "home": home,
            "away": away,
            "score": score,
            "winner": winner,
            "loser": loser,
            "winner_side": side,
            "decider": str(raw.get("decider") or raw.get("decision") or "REG").upper(),
            "scorers": _normalize_scorers(raw, home["name"], away["name"], score),
            "reasoning": str(raw.get("reasoning") or raw.get("rationale") or "").strip(),
        }
        resolved[match_no] = row
        normalized.append(row)
    return normalized


def _top_scorers(group_matches: list[dict[str, Any]], knockout_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for match in [*group_matches, *knockout_matches]:
        for scorer in match.get("scorers") or []:
            player = str(scorer.get("player") or "").strip()
            if not player or player == "未指定":
                continue
            side = scorer.get("team")
            if match.get("stage"):
                team = (match.get("home") if side == "home" else match.get("away")) or {}
                team_name = team.get("name") if isinstance(team, dict) else None
            else:
                team_name = match.get("home") if side == "home" else match.get("away")
            key = f"{player}|{team_name or ''}"
            row = counts.setdefault(key, {"player": player, "team": team_name or "", "goals": 0})
            row["goals"] += 1
    rows = list(counts.values())
    rows.sort(key=lambda row: (-row["goals"], row["player"], row["team"]))
    return rows[:20]


def _group_summary(
    group_matches: list[dict[str, Any]],
    standings: dict[str, list[dict[str, Any]]],
    qualifiers: list[dict[str, Any]],
    third_assignment: dict[str, str],
) -> dict[str, Any]:
    return {
        "group_matches": group_matches,
        "group_standings": standings,
        "third_place_qualifiers": qualifiers,
        "third_place_slot_assignment": third_assignment,
    }


def _public_sources(spec: dict[str, Any], metas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for source in spec.get("sources") or []:
        if source not in sources:
            sources.append(source)
    for meta in metas:
        for source in meta.get("sources") or []:
            if source not in sources:
                sources.append(source)
    return sources


def run_model_tournament(
    *,
    model_cfg: dict[str, Any],
    spec: dict[str, Any],
    context_pack: str,
) -> dict[str, Any]:
    model_cfg = _runtime_model_cfg(model_cfg)
    model_id = model_cfg["id"]
    setting = _model_setting(model_cfg)
    started = time.time()
    system_prompt = _build_system_prompt()
    record: dict[str, Any] = {
        "tournament_id": spec.get("tournament_id"),
        "model_id": model_id,
        "display_name": model_cfg.get("display_name"),
        "model_category": model_cfg.get("model_category"),
        "setting": setting["id"],
        "submitted_at": _now_iso(),
        "status": "ok",
        "prediction": {},
        "sources": [],
        "tokens": {"input": 0, "output": 0},
        "tool_calls": 0,
        "cost_usd": 0.0,
        "wall_seconds": 0.0,
        "error": None,
        "raw_text": {},
        "thinking_text": None,
    }

    try:
        runner = build_runner(model_cfg)
        group_parsed, group_meta = _call_json(
            runner,
            system_prompt,
            _group_prompt(spec, context_pack, model_cfg),
        )
        group_matches = _normalize_group_matches(group_parsed, spec)
        standings = compute_group_standings(group_matches, spec)
        r32_bracket, qualifiers, third_assignment = build_round_of_32(spec, standings)
        summary = _group_summary(group_matches, standings, qualifiers, third_assignment)

        knockout_parsed, knockout_meta = _call_json(
            runner,
            system_prompt,
            _knockout_prompt(spec, context_pack, model_cfg, summary, r32_bracket),
        )
        knockout_matches = _normalize_knockout_matches(knockout_parsed, spec, r32_bracket)
        final = next((m for m in knockout_matches if m["match_no"] == 104), None)
        third_place = next((m for m in knockout_matches if m["match_no"] == 103), None)
        champion = final["winner"] if final else None
        runner_up = final["loser"] if final else None

        metas = [group_meta, knockout_meta]
        record.update({
            "prediction": {
                "summary": {
                    "group_stage": str(group_parsed.get("model_tournament_summary") or "").strip(),
                    "knockout": str(knockout_parsed.get("knockout_summary") or "").strip(),
                },
                "champion": champion,
                "runner_up": runner_up,
                "third_place": third_place["winner"] if third_place else None,
                "group_matches": group_matches,
                "group_standings": standings,
                "third_place_qualifiers": qualifiers,
                "third_place_slot_assignment": third_assignment,
                "round_of_32": r32_bracket,
                "knockout_matches": knockout_matches,
                "top_scorers": _top_scorers(group_matches, knockout_matches),
            },
            "sources": _public_sources(spec, metas),
            "tokens": {
                "input": sum(meta.get("input_tokens", 0) for meta in metas),
                "output": sum(meta.get("output_tokens", 0) for meta in metas),
            },
            "tool_calls": sum(meta.get("tool_calls", 0) for meta in metas),
            "cost_usd": sum(meta.get("cost_usd", 0.0) for meta in metas),
            "raw_text": {
                "group_stage": group_meta.get("raw_text") or "",
                "knockout": knockout_meta.get("raw_text") or "",
            },
            "thinking_text": "\n".join(
                str(meta.get("thinking_text") or "") for meta in metas if meta.get("thinking_text")
            ) or None,
        })
    except Exception as exc:  # noqa: BLE001
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["wall_seconds"] = round(time.time() - started, 3)

    return record


def write_record(record: dict[str, Any], out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_id = record["model_id"]
    setting = record.get("setting") or "S1"
    path = out_dir / f"{model_id}__{setting}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return path


def cmd_run(args: argparse.Namespace) -> None:
    spec = _load_json(Path(args.spec))
    context_pack = Path(args.context_pack).read_text() if args.context_pack else ""
    models = _load_models()
    selected_ids = args.models or sorted(models)
    missing = [model_id for model_id in selected_ids if model_id not in models]
    if missing:
        raise SystemExit(f"unknown model id(s): {', '.join(missing)}")

    out_dir = Path(args.out_dir)
    print(f"[tournament] selected models: {', '.join(selected_ids)}")
    for model_id in selected_ids:
        model_cfg = models[model_id]
        setting = _model_setting(model_cfg)["id"]
        path = out_dir / f"{model_id}__{setting}.json"
        if path.exists() and not args.force:
            print(f"[tournament] skip existing {path}")
            continue
        if args.dry_run:
            print(f"[tournament] dry-run would run {model_id} ({setting})")
            continue
        print(f"[tournament] running {model_id} ({setting})")
        record = run_model_tournament(model_cfg=model_cfg, spec=spec, context_pack=context_pack)
        path = write_record(record, out_dir)
        status = record.get("status")
        champion = ((record.get("prediction") or {}).get("champion") or {}).get("name")
        detail = f", champion={champion}" if champion else ""
        print(f"[tournament] wrote {path} status={status}{detail}")


def cmd_list_models(_: argparse.Namespace) -> None:
    models = _load_models()
    for model_id, cfg in sorted(models.items()):
        print(f"{model_id}\t{_model_setting(cfg)['id']}\t{cfg.get('model_category')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run full 2026 World Cup tournament predictions.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run selected model(s) and write tournament prediction records.")
    run.add_argument("--models", nargs="*", help="Model ids to run. Defaults to every configured non-baseline model.")
    run.add_argument("--spec", default=str(SPEC_PATH), help="Tournament spec JSON path.")
    run.add_argument("--context-pack", default=str(CONTEXT_PACK), help="Injected context pack for S1 models.")
    run.add_argument("--out-dir", default=str(OUT_DIR), help="Output directory for prediction records.")
    run.add_argument("--force", action="store_true", help="Re-run even if the model record already exists.")
    run.add_argument("--dry-run", action="store_true", help="Print selected models without calling providers.")
    run.set_defaults(func=cmd_run)

    list_models = sub.add_parser("list-models", help="List tournament-capable configured models.")
    list_models.set_defaults(func=cmd_list_models)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
