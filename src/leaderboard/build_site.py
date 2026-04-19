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

    for fid_dir in sorted(RESULTS.glob("*")):
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

    main = []
    for m, v in by_model_composites.items():
        layers_mean = {k: sum(xs) / len(xs) for k, xs in by_model_layers[m].items() if xs}
        main.append({
            "model_id":    m,
            "mean":        sum(v) / len(v),
            "n":           len(v),
            "layers_mean": layers_mean,
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
        })
    return out


def build_next_match() -> dict | None:
    now = datetime.now(timezone.utc)
    registry = _load_fixtures()
    # soonest kickoff in the future
    upcoming = sorted(
        (f for f in registry if _parse_iso(f["kickoff_utc"]) > now),
        key=lambda f: _parse_iso(f["kickoff_utc"]),
    )
    for fx in upcoming:
        wca_id = fx["wca_id"]
        hdr = _load_fixture_header(wca_id)
        if not hdr:
            continue
        preds = _collect_predictions(wca_id)
        live  = _load_live_state(wca_id)
        return {"fixture": hdr, "predictions": preds, "live": live}
    # Fallback: most recent snapshot with predictions (useful for demos)
    if PREDICTIONS.exists():
        candidates = sorted(PREDICTIONS.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for d in candidates:
            hdr = _load_fixture_header(d.name)
            if hdr:
                return {"fixture": hdr, "predictions": _collect_predictions(d.name),
                        "live": _load_live_state(d.name)}
    return None


# ---------------------------------------------------------------------------
# Live state (T+0h → T+3h window)
# ---------------------------------------------------------------------------

def _load_live_state(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "live.json"
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


def _load_truth_data(wca_id: str) -> dict | None:
    path = SNAPSHOTS / wca_id / "truth.json"
    if not path.exists():
        return None
    t = json.loads(path.read_text())
    if "response" in t:
        r0 = t["response"][0]
        g = r0.get("goals") or {}
        score = None
        if g.get("home") is not None and g.get("away") is not None:
            score = f"{g['home']}-{g['away']}"
        return {"score": score, "events": r0.get("events") or []}
    return {"score": t.get("score"), "events": []}


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

    rows = []
    for wca_id in wca_ids:
        hdr = _load_fixture_header(wca_id) or {"wca_id": wca_id}

        # Only include past fixtures
        kick = hdr.get("kickoff_utc")
        if kick and _parse_iso(kick) > now:
            continue

        truth = _load_truth_data(wca_id)
        live  = _load_live_state(wca_id)

        result = None
        if truth:
            result = truth.get("score")

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
    payload = {
        "generated_at": _now_iso(),
        "leaderboard": build_leaderboard(),
        "next_match":  build_next_match(),
        "history":     build_history(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {OUT} "
          f"(leaderboard_models={len(payload['leaderboard']['main'])}, "
          f"next_match_preds={len(payload['next_match']['predictions']) if payload['next_match'] else 0}, "
          f"history={len(payload['history'])})")


if __name__ == "__main__":
    main()
