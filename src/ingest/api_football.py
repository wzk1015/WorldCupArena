"""Ingest adapter: API-Football (api-sports.io).

Pulls squads, recent form, and match events / stats used as ground truth.
Requires env var API_FOOTBALL_KEY.

This is a thin wrapper — full implementation is left for Phase 0 dry-run.
Key endpoints:
    GET /fixtures?id=<fixture_id>               fixture metadata
    GET /fixtures/events?fixture=<id>           goals / cards / subs
    GET /fixtures/lineups?fixture=<id>          starting XI + bench
    GET /fixtures/statistics?fixture=<id>       match stats
    GET /players/squads?team=<id>               squads
    GET /teams/statistics?team=<id>&season=YYYY  recent form
"""

from __future__ import annotations

from dotenv import load_dotenv
import os

load_dotenv()  # 自动加载 .env 里的所有变量
from typing import Any
import argparse
from pathlib import Path
import json
import httpx

BASE = "https://v3.football.api-sports.io"


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


def normalize_to_truth(event_resp: dict, lineup_resp: dict, stats_resp: dict,
                       fixture_meta: dict) -> dict[str, Any]:
    """Collapse API-Football responses into a WorldCupArena `truth.json` shape."""
    goals, subs, cards, own_goals, penalties = [], [], [], [], []
    for ev in event_resp.get("response", []):
        t = ev.get("type")
        time_obj = ev.get("time") or {}
        elapsed = time_obj.get("elapsed")
        extra = time_obj.get("extra") or 0
        # Leave minute as None when API-Football didn't give us a usable elapsed
        # value — the grader's truth-sanitizer will drop bad times (or ignore
        # them, depending on the metric) instead of our ingest layer silently
        # coercing unknowns to "0'".
        try:
            minute: int | None = int(elapsed) + int(extra) if elapsed is not None else None
        except (TypeError, ValueError):
            minute = None
        player = (ev.get("player") or {}).get("name")
        team_id = (ev.get("team") or {}).get("id")
        side = "home" if team_id == fixture_meta.get("home_id") else "away"
        if t == "Goal":
            detail = (ev.get("detail") or "").lower()
            bucket = own_goals if "own" in detail else penalties if "penalty" in detail else goals
            bucket.append({"player": player, "team": side, "minute": minute})
        elif t == "Card":
            color = "red" if "red" in (ev.get("detail") or "").lower() else "yellow"
            cards.append({"player": player, "team": side, "color": color, "minute": minute})
        elif t == "subst":
            subs.append({
                "team": side,
                "off": (ev.get("player") or {}).get("name"),
                "on": (ev.get("assist") or {}).get("name"),
                "minute": minute,
            })

    # compose result
    h = fixture_meta.get("home_goals", 0)
    a = fixture_meta.get("away_goals", 0)
    result = "home" if h > a else "away" if a > h else "draw"

    return {
        "score": f"{h}-{a}",
        "result": result,
        "goal_diff": h - a,
        "goals": goals,
        "own_goals": own_goals,
        "penalties": penalties,
        "cards": cards,
        "substitutions": subs,
        "scorer_names": [g["player"] for g in goals if g.get("player")],
        "lineups": lineup_resp,     # full lineup payload; grader consumes
        "stats": stats_resp,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-id", type=str, required=True)
    ap.add_argument("--out", type=str, required=True)
    args = ap.parse_args()
    
    client = APIFootballClient()
    data = client.fixture(args.fixture_id)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("saved to", args.out)


if __name__ == "__main__":
    main()
