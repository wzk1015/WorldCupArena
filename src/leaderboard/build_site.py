"""Build the data payload consumed by the project website.

Emits a single JSON file at docs/site/data.json with three sections:

    {
      "generated_at": ISO-8601 UTC,
      "leaderboard": {
          "main":              [{model_id, mean, n, layers_mean}, ...],
          "by_model_setting":  {model_id: {S1, S2}, ...}
      },
      "next_match": {
          "fixture": {wca_id, home, away, kickoff_utc, lock_at_utc, venue, stage},
          "predictions": [{model_id, setting, win_probs, most_likely_score,
                            expected_goal_diff, reasoning_overall, scorers,
                            cost_usd}, ...]
      },
      "history": [{wca_id, home, away, kickoff_utc, result, models:
                    [{model_id, setting, composite}, ...]}, ...]
    }

The site reads this file with fetch('data.json') and renders everything
client-side — no server, no build step.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "data" / "results"
PREDICTIONS = ROOT / "data" / "predictions"
SNAPSHOTS = ROOT / "data" / "snapshots"
LIVE_DIR = ROOT / "data" / "live"
SEARCH_LOGS = ROOT / "data" / "search_logs"
FIXTURES_YAML = ROOT / "configs" / "fixtures.yaml"
OUT = ROOT / "docs" / "site" / "data.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load_fixtures() -> list[dict]:
    if not FIXTURES_YAML.exists():
        return []
    cfg = yaml.safe_load(FIXTURES_YAML.read_text()) or {}
    return [f for f in (cfg.get("fixtures") or []) if f.get("enabled", True)]


# ---------------------------------------------------------------------------
# Leaderboard (all graded fixtures, aggregated by model)
# ---------------------------------------------------------------------------

def build_leaderboard() -> dict:
    by_model_composites: dict[str, list[float]] = defaultdict(list)
    by_model_layers: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_model_setting: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_model_winner_correct: dict[str, int] = defaultdict(int)
    by_model_winner_total: dict[str, int] = defaultdict(int)

    _truth_cache: dict[str, dict | None] = {}

    for fid_dir in sorted(RESULTS.glob("*")):
        wca_id = fid_dir.name
        if "_test" in wca_id.lower() or wca_id.lower().startswith("test_"):
            continue
        if wca_id not in _truth_cache:
            _truth_cache[wca_id] = _load_truth_data(wca_id)
        truth_result = (_truth_cache[wca_id] or {}).get("result")

        for f in fid_dir.glob("*.json"):
            r = json.loads(f.read_text())
            if (r.get("leakage_audit") or {}).get("leaked"):
                continue
            model = r["model_id"]
            setting = r["setting"]
            comp = float(r.get("composite", 0.0))
            by_model_composites[model].append(comp)
            by_model_setting[(model, setting)].append(comp)
            for k, v in (r.get("layers") or {}).items():
                by_model_layers[model][k].append(float(v))

            # Win prediction accuracy
            if truth_result:
                pred_file = PREDICTIONS / wca_id / f.name
                if pred_file.exists():
                    pred_rec = json.loads(pred_file.read_text())
                    wp = (pred_rec.get("prediction") or {}).get("win_probs") or {}
                    if wp:
                        predicted = max(wp, key=lambda k: wp[k])
                        by_model_winner_correct[model] += int(predicted == truth_result)
                        by_model_winner_total[model] += 1

    main = []
    for m, v in by_model_composites.items():
        layers_mean = {k: sum(xs) / len(xs) for k, xs in by_model_layers[m].items() if xs}
        total = by_model_winner_total[m]
        main.append({
            "model_id":      m,
            "mean":          sum(v) / len(v),
            "n":             len(v),
            "layers_mean":   layers_mean,
            "winner_correct": by_model_winner_correct[m],
            "winner_total":   total,
            "winner_acc":    by_model_winner_correct[m] / total if total else None,
        })
    main.sort(key=lambda x: -x["mean"])

    by_setting = {}
    for (m, s), xs in by_model_setting.items():
        by_setting.setdefault(m, {})[s] = sum(xs) / len(xs)

    return {"main": main, "by_model_setting": by_setting}


# ---------------------------------------------------------------------------
# Next match (soonest upcoming enabled fixture with predictions on disk)
# ---------------------------------------------------------------------------

def _load_fixture_header(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "fixture.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    if "response" in raw:
        r0 = raw["response"][0]
        return {
            "wca_id":      wca_id,
            "home":        r0["teams"]["home"]["name"],
            "home_logo":   r0["teams"]["home"].get("logo"),
            "away":        r0["teams"]["away"]["name"],
            "away_logo":   r0["teams"]["away"].get("logo"),
            "kickoff_utc": r0["fixture"]["date"],
            "lock_at_utc": raw.get("lock_at_utc"),
            "venue":       (r0["fixture"].get("venue") or {}).get("name"),
            "stage":       (r0.get("league") or {}).get("round"),
            "competition": (r0.get("league") or {}).get("name"),
        }
    return {
        "wca_id":      wca_id,
        "home":        raw.get("home", {}).get("name"),
        "away":        raw.get("away", {}).get("name"),
        "kickoff_utc": raw.get("kickoff_utc"),
        "lock_at_utc": raw.get("lock_at_utc"),
        "venue":       raw.get("venue"),
        "stage":       raw.get("stage"),
        "competition": raw.get("competition"),
    }


def _collect_predictions(wca_id: str) -> list[dict]:
    pred_dir = PREDICTIONS / wca_id
    out = []
    for f in sorted(pred_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        if rec.get("error"):
            continue
        p = rec.get("prediction") or {}

        # Load search sources from search_logs if available
        sources: list[dict] = []
        log_path = SEARCH_LOGS / wca_id / f.name
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text())
                sources = log.get("sources") or []
            except Exception:
                pass
        if not sources:
            sources = rec.get("sources") or []

        out.append({
            "model_id":           rec["model_id"],
            "setting":            rec["setting"],
            "win_probs":          p.get("win_probs"),
            "score_dist":         p.get("score_dist") or [],
            "most_likely_score":  p.get("most_likely_score"),
            "expected_goal_diff": p.get("expected_goal_diff"),
            "advance_prob":       p.get("advance_prob"),
            "reasoning":          p.get("reasoning") or {},
            "scorers":            p.get("scorers") or [],
            "assisters":          p.get("assisters") or [],
            "motm_probs":         p.get("motm_probs") or [],
            "lineups":            p.get("lineups") or {},
            "formations":         p.get("formations") or {},
            "substitutions":      p.get("substitutions") or [],
            "cards":              p.get("cards") or [],
            "penalties":          p.get("penalties") or [],
            "own_goals":          p.get("own_goals") or [],
            "stats":              p.get("stats") or {},
            "cost_usd":           rec.get("cost_usd"),
            "sources":            sources,
        })
    return out


def build_incoming_matches() -> list[dict]:
    """Return fixtures to display in the Incoming Matches section.

    Includes:
    - Future fixtures within the next 3 days (not yet kicked off)
    - Fixtures that have kicked off but are STILL LIVE according to data/live/
      (status != "Match Finished")

    Fixtures whose live status is "Match Finished" are excluded here and handled
    by build_history() instead.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)
    registry = _load_fixtures()
    results = []
    for fx in sorted(registry, key=lambda f: _parse_iso(f["kickoff_utc"])):
        kick = _parse_iso(fx["kickoff_utc"])
        if "_test" in fx["wca_id"].lower():
            continue
        wca_id = fx["wca_id"]

        is_future = kick > now and kick <= cutoff
        live = _load_live_state(wca_id)
        is_live = live is not None and live.get("status") != "Match Finished"
        is_finished_live = live is not None and live.get("status") == "Match Finished"

        # Skip far-future, and anything that's already finished (goes to history)
        if not is_future and not is_live:
            continue
        # If the live file says finished, skip here (history picks it up)
        if is_finished_live:
            continue

        hdr = _load_fixture_header(wca_id)
        if not hdr:
            kick_str = kick.isoformat() if hasattr(kick, "isoformat") else str(fx["kickoff_utc"])
            hdr = {
                "wca_id":      wca_id,
                "home":        fx.get("home"),
                "away":        fx.get("away"),
                "kickoff_utc": kick_str,
                "lock_at_utc": None,
                "venue":       None,
                "stage":       None,
                "competition": None,
            }
        preds = _collect_predictions(wca_id)
        results.append({"fixture": hdr, "predictions": preds, "live": live})
    return results


# ---------------------------------------------------------------------------
# Live state (T+0h → T+3h window)
# ---------------------------------------------------------------------------

def _load_live_state(wca_id: str) -> dict | None:
    path = LIVE_DIR / f"{wca_id}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    if "response" not in raw:
        return None
    r0 = raw["response"][0]
    return {
        "status":  (r0["fixture"]["status"] or {}).get("long"),
        "elapsed": (r0["fixture"]["status"] or {}).get("elapsed"),
        "score":   r0.get("goals"),   # {"home": N, "away": N}
        "events":  r0.get("events") or [],
    }


_STAT_TYPE_MAP = {
    "Ball Possession":    "possession",
    "Total Shots":        "shots",
    "Shots on Goal":      "shots_on_target",
    "Corner Kicks":       "corners",
    "Passes %":           "pass_accuracy",
    "Fouls":              "fouls",
    "Goalkeeper Saves":   "saves",
}


def _load_truth_data(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "truth.json"
    if not path.exists():
        return None
    t = json.loads(path.read_text())
    if "response" not in t:
        return {"score": t.get("score"), "result": t.get("result"), "events": []}

    r0 = t["response"][0]
    g = r0.get("goals") or {}
    hg = g.get("home")
    ag = g.get("away")
    score = f"{hg}-{ag}" if hg is not None and ag is not None else None
    result = "home" if (hg or 0) > (ag or 0) else "away" if (ag or 0) > (hg or 0) else "draw" if score else None

    teams_raw = r0.get("teams") or {}
    home_id   = (teams_raw.get("home") or {}).get("id")
    home_name = (teams_raw.get("home") or {}).get("name", "Home")
    away_name = (teams_raw.get("away") or {}).get("name", "Away")

    events = r0.get("events") or []
    scorers, assisters, cards, substitutions, own_goals, penalties = [], [], [], [], [], []
    scorer_names, assister_names = [], []
    for ev in events:
        team_id   = (ev.get("team") or {}).get("id")
        team_name = (ev.get("team") or {}).get("name", "")
        side      = "home" if team_id == home_id else "away"
        player    = (ev.get("player") or {}).get("name", "")
        assist    = (ev.get("assist") or {}).get("name")
        minute    = (ev.get("time") or {}).get("elapsed", 0)
        ev_type   = ev.get("type", "")
        detail    = ev.get("detail", "")
        if ev_type == "Goal":
            if detail == "Own Goal":
                own_goals.append({"minute": minute, "player": player, "team": side})
            elif detail == "Penalty":
                penalties.append({"minute": minute, "taker": player, "team": side, "outcome": "scored"})
                scorers.append({"minute": minute, "player": player, "team": side})
                scorer_names.append(player)
            else:
                scorers.append({"minute": minute, "player": player, "team": side})
                scorer_names.append(player)
            if assist:
                assisters.append({"player": assist, "team": side})
                assister_names.append(assist)
        elif ev_type == "Card":
            color = "yellow" if detail == "Yellow Card" else "red" if detail == "Red Card" else "second_yellow"
            cards.append({"minute": minute, "player": player, "team": side, "color": color})
        elif ev_type == "subst":
            off = player
            on  = (ev.get("assist") or {}).get("name", "")
            substitutions.append({"minute": minute, "team": side, "team_name": team_name, "off": off, "on": on})

    lineups_raw = r0.get("lineups") or []
    lineups: dict[str, dict] = {}
    formations: dict[str, str] = {}
    for side_data in lineups_raw:
        side_team_id = (side_data.get("team") or {}).get("id")
        side_key = "home" if side_team_id == home_id else "away"
        formations[side_key] = side_data.get("formation", "")
        starting = [
            {"player": (p.get("player") or {}).get("name", ""), "pos": (p.get("player") or {}).get("pos", "")}
            for p in (side_data.get("startXI") or [])
        ]
        lineups[side_key] = {"starting": starting}

    stats_raw = r0.get("statistics") or []
    stats: dict[str, dict] = {}
    for side_idx, side_key in enumerate(["home", "away"]):
        if side_idx >= len(stats_raw):
            break
        for entry in stats_raw[side_idx].get("statistics") or []:
            wca_key = _STAT_TYPE_MAP.get(entry.get("type", ""))
            if not wca_key:
                continue
            val = entry.get("value")
            if isinstance(val, str) and val.endswith("%"):
                val = float(val.rstrip("%"))
            if val is None:
                continue
            stats.setdefault(wca_key, {})[side_key] = val

    return {
        "score":          score,
        "result":         result,
        "home_name":      home_name,
        "away_name":      away_name,
        "scorer_names":   scorer_names,
        "assister_names": assister_names,
        "scorers":        scorers,
        "assisters":      assisters,
        "cards":          cards,
        "substitutions":  substitutions,
        "own_goals":      own_goals,
        "penalties":      penalties,
        "formations":     formations,
        "lineups":        lineups,
        "stats":          stats,
        "events":         events,
    }


# ---------------------------------------------------------------------------
# History (past fixtures — combines graded results with full predictions)
# ---------------------------------------------------------------------------

def build_history() -> list[dict]:
    now = datetime.now(timezone.utc)

    # Collect all known wca_ids from results + predictions dirs + yaml
    wca_ids: set[str] = set()
    if RESULTS.exists():
        wca_ids.update(d.name for d in RESULTS.glob("*") if d.is_dir())
    if PREDICTIONS.exists():
        wca_ids.update(d.name for d in PREDICTIONS.glob("*") if d.is_dir())
    for fx in _load_fixtures():
        if _parse_iso(fx["kickoff_utc"]) <= now:
            wca_ids.add(fx["wca_id"])
    # Also include fixtures whose live.json says "Match Finished" even if
    # truth.json hasn't arrived yet (grading will run on the next tick).
    if LIVE_DIR.exists():
        for lf in LIVE_DIR.glob("*.json"):
            try:
                raw = json.loads(lf.read_text())
                r0 = raw["response"][0]
                status = (r0["fixture"]["status"] or {}).get("long")
                if status == "Match Finished":
                    wca_ids.add(lf.stem)
            except Exception:
                pass

    rows = []
    for wca_id in wca_ids:
        if "_test" in wca_id.lower() or wca_id.lower().startswith("test_"):
            continue
        hdr = _load_fixture_header(wca_id) or {"wca_id": wca_id}

        # Exclude fixtures still live (they show in incoming_matches instead)
        live = _load_live_state(wca_id)
        if live and live.get("status") and live.get("status") != "Match Finished":
            continue

        # Only include past fixtures (or live-finished ones detected above)
        kick = hdr.get("kickoff_utc")
        if kick and _parse_iso(kick) > now:
            continue

        truth = _load_truth_data(wca_id)

        # If truth.json not yet available, try to build score from live.json
        result = None
        if truth:
            result = truth.get("score")
        elif live and live.get("score"):
            sc = live["score"]
            h, a = sc.get("home"), sc.get("away")
            if h is not None and a is not None:
                result = f"{h}-{a}"

        # Composite scores from results dir (for leaderboard ordering within card)
        composites: dict[str, float] = {}
        result_dir = RESULTS / wca_id
        if result_dir.exists():
            for f in result_dir.glob("*.json"):
                r = json.loads(f.read_text())
                key = f"{r['model_id']}_{r['setting']}"
                composites[key] = r.get("composite", 0.0)

        # Full predictions
        preds = _collect_predictions(wca_id)
        for p in preds:
            key = f"{p['model_id']}_{p['setting']}"
            p["composite"] = composites.get(key)

        models = sorted(
            [{"model_id": p["model_id"], "setting": p["setting"],
              "composite": composites.get(f"{p['model_id']}_{p['setting']}", 0.0)}
             for p in preds],
            key=lambda m: -(m["composite"] or 0.0),
        )

        rows.append({**hdr, "result": result, "truth": truth, "live": live,
                     "models": models, "predictions": preds})

    # Sort by kickoff descending
    rows.sort(key=lambda r: _parse_iso(r["kickoff_utc"]) if r.get("kickoff_utc") else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


def main() -> None:
    incoming = build_incoming_matches()
    payload = {
        "generated_at":     _now_iso(),
        "leaderboard":      build_leaderboard(),
        "incoming_matches": incoming,
        "history":          build_history(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Only write if content changed (ignoring generated_at), so the cron commit
    # isn't triggered purely by a timestamp update.
    def _content(p: dict) -> str:
        return json.dumps({k: v for k, v in p.items() if k != "generated_at"},
                          ensure_ascii=False, sort_keys=True)

    if OUT.exists():
        try:
            old = json.loads(OUT.read_text())
            if _content(old) == _content(payload):
                print(f"skip write — content unchanged "
                      f"(leaderboard_models={len(payload['leaderboard']['main'])}, "
                      f"incoming={len(incoming)}, "
                      f"history={len(payload['history'])})")
                return
        except Exception:
            pass  # malformed existing file — overwrite

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {OUT} "
          f"(leaderboard_models={len(payload['leaderboard']['main'])}, "
          f"incoming={len(incoming)}, "
          f"history={len(payload['history'])})")


if __name__ == "__main__":
    main()
