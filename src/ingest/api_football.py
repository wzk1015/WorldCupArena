"""Ingest adapter: API-Football (api-sports.io).

Pulls squads, recent form, and match events / stats used as ground truth.
Requires env var API_FOOTBALL_KEY.

On-disk format (snapshots/<id>/fixture.json, truth.json):
  Both files are raw API-Football /fixtures responses (the "get"/"response"/...
  wrapper) with three WorldCupArena fields added at the root level:
    fixture_id  — WorldCupArena ID set by the operator
    lock_at_utc — prediction lock time (kickoff − 1 h), added by ingest
    context_pack — squads/form/news/stats injected into S1 prompts

The orchestrator calls normalize_fixture() / normalize_to_truth() to flatten
these raw dicts into the internal formats that prompt_build and grade_match
expect. Neither function modifies the on-disk files.

Key endpoints:
    GET /fixtures?id=<fixture_id>               fixture metadata + post-match data
    GET /fixtures/events?fixture=<id>           goals / cards / subs
    GET /fixtures/lineups?fixture=<id>          starting XI + bench
    GET /fixtures/statistics?fixture=<id>       match stats
    GET /players/squads?team=<id>               squads
    GET /teams/statistics?team=<id>&season=YYYY  recent form
"""

from __future__ import annotations

from dotenv import load_dotenv
import os

load_dotenv()
from typing import Any
import argparse
from pathlib import Path
import json
import httpx

BASE = "https://v3.football.api-sports.io"

# API-Football stat type → WorldCupArena stats key
_STAT_TYPE_MAP: dict[str, str] = {
    "Ball Possession":    "possession",       # value is "69%" → 69.0
    "Total Shots":        "shots",
    "Shots on Goal":      "shots_on_target",
    "Corner Kicks":       "corners",
    "Passes %":           "pass_accuracy",    # value is "88%" → 88.0
    "Fouls":              "fouls",
    "Goalkeeper Saves":   "saves",
    # defensive_actions not directly available in match-level stats; left empty.
}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _parse_pct(v: Any) -> float | None:
    """Convert "69%" → 69.0, integer → float, None → None."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().endswith("%"):
        try:
            return float(v.strip().rstrip("%"))
        except ValueError:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_minute(time_obj: dict | None) -> int | None:
    """Return elapsed + extra minutes, or None when elapsed is missing/invalid."""
    if not time_obj:
        return None
    elapsed = time_obj.get("elapsed")
    extra = time_obj.get("extra") or 0
    try:
        return int(elapsed) + int(extra) if elapsed is not None else None
    except (TypeError, ValueError):
        return None


def normalize_fixture(raw: dict) -> dict:
    """Flatten a raw on-disk fixture.json into the internal WorldCupArena format.

    The internal format is what prompt_build.build_prompt() and the orchestrator
    consume. It is NOT written to disk — the on-disk file stays as the raw API
    response.

    Required root-level fields in raw: fixture_id, lock_at_utc.
    """
    r = raw["response"][0]
    fix = r["fixture"]
    league = r["league"]
    teams = r["teams"]

    fixture_id = raw.get("fixture_id") or str(fix["id"])

    return {
        "fixture_id":   fixture_id,
        "competition":  f"{league['name']} {league.get('season', '')}",
        "stage":        league.get("round", ""),
        "kickoff_utc":  fix["date"],
        "lock_at_utc":  raw.get("lock_at_utc", ""),
        "home": {
            "id":    str(teams["home"]["id"]),
            "name":  teams["home"]["name"],
            "short": teams["home"].get("short") or teams["home"]["name"][:3],
        },
        "away": {
            "id":    str(teams["away"]["id"]),
            "name":  teams["away"]["name"],
            "short": teams["away"].get("short") or teams["away"]["name"][:3],
        },
        "venue":        (fix.get("venue") or {}).get("name"),
        "referee":      fix.get("referee"),
        "context_pack": raw.get("context_pack") or {},
        "snapshot_hash": raw.get("snapshot_hash"),
    }


def normalize_to_truth(raw: dict) -> dict:
    """Flatten a raw on-disk truth.json into the WorldCupArena truth format.

    The truth format is what grade_match.grade_match() consumes:
      score, result, goal_diff, goals, own_goals, penalties, cards,
      substitutions, scorer_names, assister_names, lineups, formations,
      stats, motm, advanced.

    Notes on specific fields:
      - motm: not available from the /fixtures endpoint; always None.
      - advanced: set to True/False/None based on whether the home team
        won this leg (useful for 2-leg knockout fixtures where the home
        side has home advantage on aggregate).
      - defensive_actions stat: not present in match-level statistics;
        set to {} so the grader's smape check falls back to 0 (no truth).
    """
    r = raw["response"][0]
    teams = r["teams"]
    goals_raw = r.get("goals") or {}
    events = r.get("events") or []
    lineups_raw = r.get("lineups") or []
    statistics = r.get("statistics") or []

    home_id = teams["home"]["id"]

    def _side(team_id: int | None) -> str:
        return "home" if team_id == home_id else "away"

    # ---- score / result ----
    h = int(goals_raw.get("home") or 0)
    a = int(goals_raw.get("away") or 0)
    result = "home" if h > a else "away" if a > h else "draw"

    # ---- events ----
    goals, subs, cards, own_goals, penalties = [], [], [], [], []
    for ev in events:
        time_obj = ev.get("time")
        minute = _safe_minute(time_obj)
        # Negative elapsed is invalid data from the API — treat as None.
        if minute is not None and minute < 0:
            minute = None

        player = (ev.get("player") or {}).get("name")
        team_id = (ev.get("team") or {}).get("id")
        side = _side(team_id)
        assist_name = (ev.get("assist") or {}).get("name") or None

        ev_type = ev.get("type")
        detail = (ev.get("detail") or "").lower()

        if ev_type == "Goal":
            entry: dict[str, Any] = {"player": player, "team": side, "minute": minute}
            if assist_name:
                entry["assist"] = assist_name
            if "own goal" in detail:
                own_goals.append(entry)
            elif "penalty" in detail:
                penalties.append(entry)
            else:
                goals.append(entry)

        elif ev_type == "Card":
            color = "red" if "red card" in detail else "yellow"
            cards.append({"player": player, "team": side, "color": color, "minute": minute})

        elif ev_type == "subst":
            # API-Football convention: player = coming OFF, assist = coming ON.
            on = assist_name
            off = player
            subs.append({"team": side, "off": off, "on": on, "minute": minute})

    # ---- lineups ----
    lineups: dict[str, Any] = {}
    formations: dict[str, str | None] = {}
    for entry in lineups_raw:
        tid = (entry.get("team") or {}).get("id")
        side = _side(tid)

        def _extract(players_list: list) -> list[dict[str, str]]:
            out = []
            for item in players_list or []:
                p = item.get("player") or {}
                name = p.get("name")
                pos = p.get("pos")
                if name:
                    out.append({"name": name, "position": pos or "?"})
            return out

        lineups[side] = {
            "starting": _extract(entry.get("startXI") or []),
            "bench":    _extract(entry.get("substitutes") or []),
        }
        formations[side] = entry.get("formation")

    # ---- match statistics ----
    stats: dict[str, dict[str, float]] = {k: {} for k in _STAT_TYPE_MAP.values()}
    stats["defensive_actions"] = {}  # not available at match level

    for team_stats in statistics:
        tid = (team_stats.get("team") or {}).get("id")
        side = _side(tid)
        for stat in team_stats.get("statistics") or []:
            stat_type = stat.get("type")
            wca_key = _STAT_TYPE_MAP.get(stat_type)
            if wca_key is None:
                continue
            val = _parse_pct(stat.get("value"))
            if val is not None:
                stats[wca_key][side] = val

    return {
        "score":          f"{h}-{a}",
        "result":         result,
        "goal_diff":      h - a,
        "goals":          goals,
        "own_goals":      own_goals,
        "penalties":      penalties,
        "cards":          cards,
        "substitutions":  subs,
        "scorer_names":   [g["player"] for g in goals if g.get("player")],
        "assister_names": [g["assist"] for g in goals if g.get("assist")],
        "lineups":        lineups,
        "formations":     formations,
        "stats":          stats,
        "motm":           None,   # not available from /fixtures endpoint
        "advanced":       teams["home"].get("winner"),  # True/False/None
    }


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class APIFootballClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["API_FOOTBALL_KEY"]
        self._h = {"x-apisports-key": self.api_key}

    def _get(self, path: str, **params) -> dict[str, Any]:
        with httpx.Client(base_url=BASE, headers=self._h, timeout=30.0) as c:
            r = c.get(path, params=params)
            r.raise_for_status()
            return r.json()

    def fixture(self, fixture_id: int) -> dict[str, Any]:
        return self._get("/fixtures", id=fixture_id)

    def events(self, fixture_id: int) -> dict[str, Any]:
        return self._get("/fixtures/events", fixture=fixture_id)

    def lineups(self, fixture_id: int) -> dict[str, Any]:
        return self._get("/fixtures/lineups", fixture=fixture_id)

    def statistics(self, fixture_id: int) -> dict[str, Any]:
        return self._get("/fixtures/statistics", fixture=fixture_id)

    def squad(self, team_id: int) -> dict[str, Any]:
        return self._get("/players/squads", team=team_id)

    def team_stats(self, team_id: int, season: int, league: int) -> dict[str, Any]:
        return self._get("/teams/statistics", team=team_id, season=season, league=league)

    def team_recent_fixtures(self, team_id: int, last: int = 10) -> dict[str, Any]:
        """Last N completed fixtures for a team across all competitions."""
        return self._get("/fixtures", team=team_id, last=last, status="FT-AET-PEN")


# ---------------------------------------------------------------------------
# context_pack population
# ---------------------------------------------------------------------------

def _normalize_squad(raw_squad: dict) -> dict[str, Any]:
    """Convert /players/squads response to context_pack.squads[side] shape."""
    resp = (raw_squad.get("response") or [{}])[0]
    team_name = (resp.get("team") or {}).get("name", "?")
    players = []
    for p in resp.get("players") or []:
        players.append({
            "name":     p.get("name"),
            "position": p.get("position"),
            "age":      p.get("age"),
            "club":     team_name,  # for national teams this would differ; fine for clubs
            "number":   p.get("number"),
        })
    return {"team_name": team_name, "players": players}


def _normalize_recent_form(raw_fixtures: dict, team_id: int, last: int = 10) -> dict[str, Any]:
    """Convert /fixtures?team=<id>&last=N to context_pack.recent_form[side] shape."""
    matches = []
    for r in (raw_fixtures.get("response") or [])[:last]:
        league = r.get("league") or {}
        teams = r.get("teams") or {}
        goals = r.get("goals") or {}
        fix = r.get("fixture") or {}

        home_id = (teams.get("home") or {}).get("id")
        is_home = home_id == team_id
        opponent_obj = teams.get("away") if is_home else teams.get("home")
        opponent = (opponent_obj or {}).get("name", "?")

        h = goals.get("home") or 0
        a = goals.get("away") or 0
        if is_home:
            gf, ga = h, a
        else:
            gf, ga = a, h
        result = "W" if gf > ga else "L" if gf < ga else "D"

        matches.append({
            "date":        (fix.get("date") or "")[:10],
            "competition": league.get("name", "?"),
            "opponent":    opponent,
            "venue":       "H" if is_home else "A",
            "result":      result,
            "score":       f"{gf}-{ga}",
        })

    last_n = len(matches)
    wins   = sum(1 for m in matches if m["result"] == "W")
    draws  = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    summary = f"{wins}W {draws}D {losses}L (last {last_n})"

    return {"summary": summary, "matches": matches}


def _aggregate_stats(raw_fixtures: dict, team_id: int) -> dict[str, Any]:
    """Compute rolling averages from recent fixtures' match-level statistics."""
    totals: dict[str, list[float]] = {}
    for r in raw_fixtures.get("response") or []:
        for team_stat in r.get("statistics") or []:
            tid = (team_stat.get("team") or {}).get("id")
            if tid != team_id:
                continue
            for stat in team_stat.get("statistics") or []:
                wca_key = _STAT_TYPE_MAP.get(stat.get("type"))
                if wca_key is None:
                    continue
                val = _parse_pct(stat.get("value"))
                if val is not None:
                    totals.setdefault(wca_key, []).append(val)

    return {k: round(sum(v) / len(v), 1) for k, v in totals.items() if v}


def populate_context_pack(
    fixture_path: "Path",
    client: APIFootballClient,
    recent_n: int = 10,
) -> None:
    """Fetch squads, recent form, and rolling stats and write them into
    fixture_path's context_pack.  News headlines are NOT populated here —
    they come from a separate news-API ingest step (not yet implemented).

    Mutates the fixture.json on disk in-place.
    """
    import json
    from pathlib import Path

    path = Path(fixture_path)
    raw = json.loads(path.read_text())
    r0 = raw["response"][0]
    home_id = r0["teams"]["home"]["id"]
    away_id = r0["teams"]["away"]["id"]

    print(f"  fetching squads…")
    home_squad_raw = client.squad(home_id)
    away_squad_raw = client.squad(away_id)

    print(f"  fetching recent fixtures (home)…")
    home_recent_raw = client.team_recent_fixtures(home_id, last=recent_n)
    print(f"  fetching recent fixtures (away)…")
    away_recent_raw = client.team_recent_fixtures(away_id, last=recent_n)

    cp = raw.get("context_pack") or {}
    cp["squads"] = {
        "home": _normalize_squad(home_squad_raw),
        "away": _normalize_squad(away_squad_raw),
    }
    cp["recent_form"] = {
        "home": _normalize_recent_form(home_recent_raw, home_id, last=recent_n),
        "away": _normalize_recent_form(away_recent_raw, away_id, last=recent_n),
    }
    cp["stats_last_n"] = {
        "home": _aggregate_stats(home_recent_raw, home_id),
        "away": _aggregate_stats(away_recent_raw, away_id),
        "n":    recent_n,
    }
    # news_headlines: populated separately (no API-Football endpoint for news)
    cp.setdefault("news_headlines", [])

    raw["context_pack"] = cp
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    print(f"  context_pack written to {path}")


# ---------------------------------------------------------------------------
# CLI — fetch and save raw fixture response
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fetch a fixture from API-Football and save the raw response.")
    ap.add_argument("--fixture-id", type=int, required=True, help="API-Football fixture ID")
    ap.add_argument("--wca-id", type=str, required=True, help="WorldCupArena fixture_id (e.g. ucl_sf1_l1)")
    ap.add_argument("--lock-at", type=str, required=True, help="lock_at_utc (ISO-8601, kickoff − 1 h)")
    ap.add_argument("--out", type=str, required=True, help="Output path (e.g. data/snapshots/ucl_sf1_l1/fixture.json)")
    args = ap.parse_args()

    client = APIFootballClient()
    data = client.fixture(args.fixture_id)
    # Inject WorldCupArena extra fields
    data["fixture_id"] = args.wca_id
    data["lock_at_utc"] = args.lock_at
    data.setdefault("context_pack", {})

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"saved to {args.out}")


if __name__ == "__main__":
    main()
