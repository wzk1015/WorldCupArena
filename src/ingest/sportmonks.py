"""SportMonks Football API v3 adapter.

The rest of WorldCupArena consumes an API-Football-like raw fixture shape.
This adapter fetches SportMonks fixtures and converts them into that shape so
existing prompt building, live updates, truth grading, and site generation can
keep using the same normalization code.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

import httpx

BASE = "https://api.sportmonks.com/v3/football"

FIXTURE_INCLUDE = ";".join([
    "participants",
    "scores",
    "state",
    "league",
    "season",
    "stage",
    "round",
    "venue",
    "events.type",
    "lineups.type",
    "lineups.player",
    "statistics.type",
])

RECENT_INCLUDE = ";".join([
    "participants",
    "scores",
    "state",
    "league",
    "season",
    "stage",
    "statistics.type",
])

SQUAD_INCLUDE = "player;position"

SPORTMONKS_STAT_TYPE_MAP: dict[str, str] = {
    "ball possession": "Ball Possession",
    "possession": "Ball Possession",
    "total shots": "Total Shots",
    "shots total": "Total Shots",
    "shots": "Total Shots",
    "shots on target": "Shots on Goal",
    "shots on goal": "Shots on Goal",
    "corners": "Corner Kicks",
    "corner kicks": "Corner Kicks",
    "accurate passes percentage": "Passes %",
    "passes percentage": "Passes %",
    "pass accuracy": "Passes %",
    "fouls": "Fouls",
    "saves": "Goalkeeper Saves",
    "goalkeeper saves": "Goalkeeper Saves",
}

POSITION_MAP = {
    "goalkeeper": "Goalkeeper",
    "keeper": "Goalkeeper",
    "defender": "Defender",
    "midfielder": "Midfielder",
    "attacker": "Attacker",
    "forward": "Attacker",
}

STATUS_LONG = {
    "NS": "Not Started",
    "NOT_STARTED": "Not Started",
    "LIVE": "In Play",
    "INPLAY": "In Play",
    "HT": "Halftime",
    "FT": "Match Finished",
    "FT_PEN": "Match Finished",
    "AET": "Match Finished",
    "POSTPONED": "Match Postponed",
    "CANCELLED": "Match Cancelled",
}


def _dt_utc(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().replace(" ", "T", 1)
    if text.endswith("Z") or "+" in text[10:]:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _date_only(value: str | None) -> str:
    iso = _dt_utc(value)
    return iso[:10] if iso else ""


def _participant_by_location(fixture: dict[str, Any], location: str) -> dict[str, Any]:
    for participant in fixture.get("participants") or []:
        if ((participant.get("meta") or {}).get("location") or "").lower() == location:
            return participant
    parts = fixture.get("participants") or []
    idx = 0 if location == "home" else 1
    return parts[idx] if idx < len(parts) else {}


def _participant_side_map(fixture: dict[str, Any]) -> dict[int, str]:
    out: dict[int, str] = {}
    for side in ("home", "away"):
        participant = _participant_by_location(fixture, side)
        if participant.get("id") is not None:
            out[int(participant["id"])] = side
    return out


def _team_payload(participant: dict[str, Any]) -> dict[str, Any]:
    meta = participant.get("meta") or {}
    return {
        "id": participant.get("id"),
        "name": participant.get("name"),
        "logo": participant.get("image_path"),
        "winner": meta.get("winner"),
    }


def _score_pair(fixture: dict[str, Any]) -> dict[str, int | None]:
    scores = fixture.get("scores") or []
    preferred = ["CURRENT", "2ND_HALF", "FT", "AET", "FULL_TIME", "1ST_HALF"]
    for desc in preferred:
        pair: dict[str, int | None] = {"home": None, "away": None}
        for row in scores:
            if str(row.get("description") or "").upper() != desc:
                continue
            score = row.get("score") or {}
            side = score.get("participant")
            if side in pair:
                pair[side] = score.get("goals")
        if pair["home"] is not None or pair["away"] is not None:
            return pair
    return {"home": None, "away": None}


def _status(fixture: dict[str, Any]) -> dict[str, Any]:
    state = fixture.get("state") or {}
    code = str(state.get("state") or state.get("developer_name") or state.get("short_name") or "").upper()
    name = state.get("name") or STATUS_LONG.get(code) or code or None
    return {
        "long": STATUS_LONG.get(code, name),
        "short": state.get("short_name") or code or None,
        "elapsed": None,
    }


def _event_type_name(event: dict[str, Any]) -> str:
    type_obj = event.get("type") or {}
    return " ".join(
        str(type_obj.get(k) or event.get(k) or "")
        for k in ("developer_name", "name")
    ).strip().lower()


def _event_minute(event: dict[str, Any]) -> tuple[int | None, int | None]:
    minute = event.get("minute")
    extra = event.get("extra_minute") or event.get("additional_minute")
    try:
        minute = int(minute) if minute is not None else None
    except (TypeError, ValueError):
        minute = None
    try:
        extra = int(extra) if extra is not None else None
    except (TypeError, ValueError):
        extra = None
    return minute, extra


def _convert_event(event: dict[str, Any], side_by_participant: dict[int, str], teams: dict[str, Any]) -> dict[str, Any] | None:
    participant_id = event.get("participant_id") or event.get("team_id")
    side = side_by_participant.get(int(participant_id)) if participant_id is not None else None
    if side not in {"home", "away"}:
        return None
    team = teams[side]
    minute, extra = _event_minute(event)
    type_name = _event_type_name(event)
    player_name = event.get("player_name") or (event.get("player") or {}).get("name")
    related_name = event.get("related_player_name") or (event.get("related_player") or {}).get("name")

    out = {
        "time": {"elapsed": minute, "extra": extra},
        "team": {"id": team.get("id"), "name": team.get("name"), "logo": team.get("logo")},
        "player": {"id": event.get("player_id"), "name": player_name},
        "assist": {"id": event.get("related_player_id"), "name": related_name},
        "comments": event.get("info") or event.get("addition") or event.get("result"),
    }

    if "substitution" in type_name or "substitute" in type_name:
        out.update({"type": "subst", "detail": "Substitution"})
    elif "yellow" in type_name:
        out.update({"type": "Card", "detail": "Yellow Card"})
    elif "red" in type_name:
        detail = "Second Yellow Card" if "second" in type_name else "Red Card"
        out.update({"type": "Card", "detail": detail})
    elif "own" in type_name and "goal" in type_name:
        out.update({"type": "Goal", "detail": "Own Goal"})
    elif "penalty" in type_name and "goal" in type_name:
        out.update({"type": "Goal", "detail": "Penalty"})
    elif "goal" in type_name:
        out.update({"type": "Goal", "detail": "Normal Goal"})
    elif "var" in type_name:
        out.update({"type": "Var", "detail": event.get("info") or (event.get("type") or {}).get("name") or "VAR"})
    else:
        out.update({"type": (event.get("type") or {}).get("name") or "Event", "detail": event.get("info") or ""})
    return out


def _convert_lineups(fixture: dict[str, Any], teams: dict[str, Any]) -> list[dict[str, Any]]:
    side_by_participant = _participant_side_map(fixture)
    grouped = {
        "home": {"team": teams["home"], "formation": None, "startXI": [], "substitutes": []},
        "away": {"team": teams["away"], "formation": None, "startXI": [], "substitutes": []},
    }
    for row in fixture.get("lineups") or []:
        participant_id = row.get("participant_id") or row.get("team_id")
        side = side_by_participant.get(int(participant_id)) if participant_id is not None else None
        if side not in grouped:
            continue
        type_obj = row.get("type") or {}
        type_name = " ".join(str(type_obj.get(k) or "") for k in ("developer_name", "name")).lower()
        player = row.get("player") or {}
        position = row.get("position") or row.get("detailed_position") or {}
        pos_name = position.get("name") or position.get("developer_name") or row.get("position_name") or ""
        player_payload = {
            "player": {
                "id": row.get("player_id") or player.get("id"),
                "name": row.get("player_name") or player.get("name") or player.get("display_name"),
                "number": row.get("jersey_number") or row.get("number"),
                "pos": POSITION_MAP.get(str(pos_name).casefold(), pos_name or ""),
            }
        }
        if "bench" in type_name or "substitute" in type_name:
            grouped[side]["substitutes"].append(player_payload)
        else:
            grouped[side]["startXI"].append(player_payload)
    return [grouped["home"], grouped["away"]]


def _stat_type(row: dict[str, Any]) -> str | None:
    type_obj = row.get("type") or {}
    candidates = [
        type_obj.get("developer_name"),
        type_obj.get("name"),
        row.get("type_name"),
        row.get("name"),
    ]
    for candidate in candidates:
        key = str(candidate or "").replace("_", " ").casefold().strip()
        if key in SPORTMONKS_STAT_TYPE_MAP:
            return SPORTMONKS_STAT_TYPE_MAP[key]
    return None


def _stat_value(row: dict[str, Any]) -> Any:
    data = row.get("data") or {}
    value = data.get("value", row.get("value"))
    if isinstance(value, dict):
        value = value.get("total") or value.get("count") or value.get("value")
    if isinstance(value, str) and value.endswith("%"):
        return value
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    stat_name = (_stat_type(row) or "").lower()
    if stat_name in {"ball possession", "passes %"} and 0 <= num <= 1:
        return f"{round(num * 100, 1)}%"
    if stat_name in {"ball possession", "passes %"}:
        return f"{round(num, 1)}%"
    return int(num) if num.is_integer() else round(num, 1)


def _convert_statistics(fixture: dict[str, Any], teams: dict[str, Any]) -> list[dict[str, Any]]:
    side_by_participant = _participant_side_map(fixture)
    grouped = {
        "home": {"team": teams["home"], "statistics": []},
        "away": {"team": teams["away"], "statistics": []},
    }
    for row in fixture.get("statistics") or []:
        participant_id = row.get("participant_id") or row.get("team_id")
        side = side_by_participant.get(int(participant_id)) if participant_id is not None else None
        stat_type = _stat_type(row)
        if side not in grouped or not stat_type:
            continue
        grouped[side]["statistics"].append({"type": stat_type, "value": _stat_value(row)})
    return [grouped["home"], grouped["away"]]


def sportmonks_fixture_to_api_football(raw: dict[str, Any]) -> dict[str, Any]:
    fixture = raw.get("data") or raw
    home = _participant_by_location(fixture, "home")
    away = _participant_by_location(fixture, "away")
    teams = {"home": _team_payload(home), "away": _team_payload(away)}
    goals = _score_pair(fixture)
    league = fixture.get("league") or {}
    season = fixture.get("season") or {}
    stage = fixture.get("stage") or {}
    round_obj = fixture.get("round") or {}
    venue = fixture.get("venue") or {}
    side_by_participant = _participant_side_map(fixture)

    events = []
    for event in fixture.get("events") or []:
        converted = _convert_event(event, side_by_participant, teams)
        if converted:
            events.append(converted)

    league_round = stage.get("name") or round_obj.get("name") or fixture.get("leg") or ""
    season_name = season.get("name") or season.get("year") or ""
    kickoff = _dt_utc(fixture.get("starting_at"))

    return {
        "get": "fixtures",
        "parameters": {"id": str(fixture.get("id"))},
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": [{
            "fixture": {
                "id": fixture.get("id"),
                "referee": None,
                "timezone": "UTC",
                "date": kickoff,
                "timestamp": fixture.get("starting_at_timestamp"),
                "periods": {"first": None, "second": None},
                "venue": {
                    "id": venue.get("id") or fixture.get("venue_id"),
                    "name": venue.get("name"),
                    "city": venue.get("city_name") or venue.get("city"),
                },
                "status": _status(fixture),
            },
            "league": {
                "id": league.get("id") or fixture.get("league_id"),
                "name": league.get("name"),
                "country": league.get("country_name") or "World",
                "logo": league.get("image_path"),
                "season": season_name,
                "round": league_round,
            },
            "teams": teams,
            "goals": goals,
            "score": {
                "halftime": {"home": None, "away": None},
                "fulltime": goals,
                "extratime": {"home": None, "away": None},
                "penalty": {"home": None, "away": None},
            },
            "events": events,
            "lineups": _convert_lineups(fixture, teams),
            "statistics": _convert_statistics(fixture, teams),
        }],
        "_provider": "sportmonks",
        "_sportmonks_raw": fixture,
    }


def _squad_to_api_football(raw: dict[str, Any], team_id: int) -> dict[str, Any]:
    players = []
    team_name = str(team_id)
    for row in raw.get("data") or []:
        player = row.get("player") or {}
        position = row.get("position") or {}
        pos_name = position.get("name") or position.get("developer_name") or ""
        if player.get("name"):
            players.append({
                "id": player.get("id"),
                "name": player.get("name"),
                "age": None,
                "number": row.get("jersey_number"),
                "position": POSITION_MAP.get(str(pos_name).casefold(), pos_name or None),
                "photo": player.get("image_path"),
            })
    return {"response": [{"team": {"id": team_id, "name": team_name}, "players": players}]}


class SportMonksClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["SPORTMONKS_API_KEY"]

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        clean["api_token"] = self.api_key
        with httpx.Client(base_url=BASE, timeout=45.0) as client:
            response = client.get(path, params=clean)
            response.raise_for_status()
            return response.json()

    def fixture(self, fixture_id: int | str) -> dict[str, Any]:
        raw = self._get(f"/fixtures/{fixture_id}", include=FIXTURE_INCLUDE)
        return sportmonks_fixture_to_api_football(raw)

    def squad(self, team_id: int | str) -> dict[str, Any]:
        raw = self._get(f"/squads/teams/{team_id}", include=SQUAD_INCLUDE)
        converted = _squad_to_api_football(raw, int(team_id))
        team_name = self._team_name_from_squad(raw)
        if team_name:
            converted["response"][0]["team"]["name"] = team_name
        return converted

    def _team_name_from_squad(self, raw: dict[str, Any]) -> str | None:
        # Squad rows usually omit team details; keep the fixture header names in prompts.
        return None

    def team_stats(self, team_id: int, season: int, league: int) -> dict[str, Any]:
        return {"response": []}

    def team_recent_fixtures(self, team_id: int | str, last: int = 10) -> dict[str, Any]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=900)
        raw = self._get(
            f"/fixtures/between/{start.isoformat()}/{end.isoformat()}/{team_id}",
            include=RECENT_INCLUDE,
        )
        rows = raw.get("data") or []
        rows.sort(key=lambda item: item.get("starting_at") or "", reverse=True)
        converted = [sportmonks_fixture_to_api_football({"data": item})["response"][0] for item in rows[:last]]
        return {"response": converted}
