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
        scorers = [s.get("player") for s in (p.get("scorers") or [])[:3] if s.get("player")]
        out.append({
            "model_id":          rec["model_id"],
            "setting":           rec["setting"],
            "win_probs":         p.get("win_probs"),
            "most_likely_score": p.get("most_likely_score"),
            "expected_goal_diff": p.get("expected_goal_diff"),
            "advance_prob":      p.get("advance_prob"),
            "reasoning_overall": (p.get("reasoning") or {}).get("overall"),
            "top_scorers":       scorers,
            "cost_usd":          rec.get("cost_usd"),
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
        return {"fixture": hdr, "predictions": preds}
    # Fallback: most recent snapshot with predictions (useful for demos)
    if PREDICTIONS.exists():
        candidates = sorted(PREDICTIONS.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for d in candidates:
            hdr = _load_fixture_header(d.name)
            if hdr:
                return {"fixture": hdr, "predictions": _collect_predictions(d.name)}
    return None


# ---------------------------------------------------------------------------
# History (graded fixtures)
# ---------------------------------------------------------------------------

def build_history() -> list[dict]:
    rows = []
    for fid_dir in sorted(RESULTS.glob("*"), reverse=True):
        hdr = _load_fixture_header(fid_dir.name) or {"wca_id": fid_dir.name}
        truth_path = SNAPSHOTS / fid_dir.name / "truth.json"
        result = None
        if truth_path.exists():
            t = json.loads(truth_path.read_text())
            if "response" in t:
                r0 = t["response"][0]
                g = r0.get("goals") or {}
                if g.get("home") is not None and g.get("away") is not None:
                    result = f"{g['home']}-{g['away']}"
            else:
                result = t.get("score")
        models = []
        for f in fid_dir.glob("*.json"):
            r = json.loads(f.read_text())
            models.append({
                "model_id":  r["model_id"],
                "setting":   r["setting"],
                "composite": r.get("composite", 0.0),
            })
        models.sort(key=lambda m: -m["composite"])
        rows.append({**hdr, "result": result, "models": models})
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
