"""Top-level grader: takes a prediction JSON + ground-truth JSON for a single match,
walks configs/tasks.yaml, invokes the appropriate metric per task, returns a
structured score object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import metrics

ROOT = Path(__file__).resolve().parents[2]
TASKS_YAML = ROOT / "configs" / "tasks.yaml"


def load_tasks() -> dict[str, Any]:
    return yaml.safe_load(TASKS_YAML.read_text())


METRIC_FNS = {
    "brier_3way":          lambda p, t: metrics.brier_3way(p["win_probs"], t["result"]),
    "brier_binary":        lambda p, t: metrics.brier_binary(p.get("advance_prob", 0.5), t.get("advanced", False)),
    "brier_multiclass":    lambda p, t: metrics.brier_multiclass(p.get("champion_probs", {}), t.get("champion", "")),
    "rps_score":           lambda p, t: metrics.rps_score(p["score_dist"], t["score"]),
    "mae":                 lambda p, t: metrics.mae(p.get("expected_goal_diff", 0), t.get("goal_diff", 0)),
    "smape":               lambda p, t: metrics.smape(p.get("value", 0), t.get("value", 0)),
    "f1_set":              lambda p, t: metrics.f1_set(p.get("pred_set", []), t.get("truth_set", [])),
    "jaccard_with_position": None,   # specialized below
    "exact_match":         lambda p, t: metrics.exact_match(p.get("value"), t.get("value")),
    "top1_accuracy":       lambda p, t: metrics.top1_accuracy(p.get("ranking", []), t.get("winner", "")),
    "f1_with_ndcg":        None,     # specialized below
    "event_f1":            lambda p, t: metrics.f1_set(
        _event_keys(p.get("events", [])), _event_keys(t.get("events", []))
    ),
    "hungarian_minute_mae": lambda p, t: metrics.hungarian_minute_mae(p.get("events", []), t.get("events", [])),
    "kendall_tau":         lambda p, t: metrics.kendall_tau(p.get("pred_order", []), t.get("truth_order", [])),
    "ndcg_at_3":           lambda p, t: metrics.ndcg_at_k(p.get("ranking", []), t.get("truth_ranking", []), 3),
    "bracket_score":       lambda p, t: metrics.bracket_score(p.get("bracket", {}), t.get("bracket", {})),
}


def _norm(name: str | None) -> str:
    """Normalize a player name for comparison (delegates to metrics._norm_name)."""
    return metrics._norm_name(name or "")


def _event_keys(events: list[dict[str, Any]]) -> list[str]:
    """Bucket events by (player_norm, 5-minute window) for set-based f1 scoring.

    Events with an unusable minute (None, non-numeric, negative) are skipped
    rather than bucketed — upstream truth sanitization will already have
    dropped ones we're unwilling to score at all; any remaining here came
    from predictions and we simply can't place them on the timeline.
    """
    keys: list[str] = []
    for e in events or []:
        player = _norm(e.get("player") or "?")
        raw = e.get("minute")
        if raw is None:
            mr = e.get("minute_range")
            if isinstance(mr, (list, tuple)) and len(mr) == 2:
                try:
                    raw = (float(mr[0]) + float(mr[1])) / 2
                except (TypeError, ValueError):
                    raw = None
        try:
            minute = float(raw)
        except (TypeError, ValueError):
            continue
        if minute < 0:
            continue
        keys.append(f"{player}@{int(minute) // 5}")
    return keys


def _stats_smape(pred: dict[str, Any], truth: dict[str, Any], key: str) -> float:
    p_obj = (pred.get("stats") or {}).get(key) or {}
    t_obj = (truth.get("stats") or {}).get(key) or {}
    sides = ["home", "away"]
    scores = [metrics.smape(p_obj.get(s, 0), t_obj.get(s, 0)) for s in sides if s in t_obj]
    return sum(scores) / len(scores) if scores else 0.0


def _f1_with_ndcg(pred_scorers: list[dict[str, Any]], truth_scorers: list[str]) -> float:
    pred_names = [_norm(s.get("player")) for s in pred_scorers]
    truth_norm = [_norm(n) for n in truth_scorers]
    f1 = metrics.f1_set(pred_names, truth_norm)
    ranked = sorted(pred_scorers, key=lambda s: -float(s.get("p", 0)))
    ndcg = metrics.ndcg_at_k([_norm(s["player"]) for s in ranked], truth_norm, k=3)
    return 0.6 * f1 + 0.4 * ndcg


def _jaccard_with_position(pred_lineups: dict[str, Any], truth_lineups: dict[str, Any]) -> float:
    per_side = []
    for side in ("home", "away"):
        p = pred_lineups.get(side, {}).get("starting", [])
        t = truth_lineups.get(side, {}).get("starting", [])
        set_score = metrics.jaccard([_norm(x.get("name")) for x in p], [_norm(x.get("name")) for x in t])
        pos_match = sum(
            1 for a in p for b in t
            if _norm(a.get("name")) == _norm(b.get("name")) and a.get("position") == b.get("position")
        )
        pos_score = 100.0 * pos_match / 11
        per_side.append(0.7 * set_score + 0.3 * pos_score)
    return sum(per_side) / len(per_side) if per_side else 0.0


def grade_match(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Return a per-task score dict and a composite score."""
    cfg = load_tasks()
    per_task: dict[str, float] = {}

    for task in cfg["tasks"]:
        tid = task["id"]
        metric = task["metric"]
        score: float = 0.0
        try:
            if metric in ("brier_3way",):
                score = metrics.brier_3way(prediction.get("win_probs", {}), truth.get("result", ""))
            elif metric == "rps_score" and prediction.get("score_dist"):
                score = metrics.rps_score(prediction["score_dist"], truth["score"])
            elif metric == "mae" and tid == "goal_diff_mae":
                score = metrics.mae(prediction.get("expected_goal_diff", 0), truth.get("goal_diff", 0))
            elif metric == "brier_binary":
                score = metrics.brier_binary(prediction.get("advance_prob", 0.5), truth.get("advanced", False))
            elif metric == "jaccard_with_position":
                score = _jaccard_with_position(prediction.get("lineups", {}), truth.get("lineups", {}))
            elif metric == "exact_match" and tid == "formation":
                pred_f = (prediction.get("formations") or {})
                truth_f = (truth.get("formations") or {})
                sides = [metrics.exact_match(pred_f.get(s), truth_f.get(s)) for s in ("home", "away")]
                score = sum(sides) / len(sides) if sides else 0.0
            elif metric == "f1_with_ndcg":
                score = _f1_with_ndcg(
                    prediction.get("scorers", []) or [],
                    truth.get("scorer_names", []) or [],
                )
            elif metric == "f1_set" and tid == "assist_providers":
                pred_a = [_norm(a.get("player")) for a in prediction.get("assisters", []) or []]
                score = metrics.f1_set(pred_a, [_norm(n) for n in truth.get("assister_names", []) or []])
            elif metric == "top1_accuracy" and tid == "man_of_the_match":
                ranked = sorted(prediction.get("motm_probs", []) or [],
                                key=lambda x: -float(x.get("p", 0)))
                top1 = _norm(ranked[0].get("player")) if ranked else None
                score = metrics.top1_accuracy([top1] if top1 else [], _norm(truth.get("motm", "")))
            elif metric == "hungarian_minute_mae" and tid == "goal_minute":
                score = metrics.hungarian_minute_mae(
                    prediction.get("scorers", []) or [],
                    truth.get("goals", []) or [],
                )
            elif metric == "hungarian_minute_mae" and tid == "substitution_times":
                score = metrics.hungarian_minute_mae(
                    prediction.get("substitutions", []) or [],
                    truth.get("substitutions", []) or [],
                    key="on",
                )
            elif metric == "event_f1":
                field_map = {"cards": "cards",
                             "penalty_events": "penalties",
                             "own_goals": "own_goals"}
                pred_ev = prediction.get(field_map.get(tid, tid), []) or []
                truth_ev = truth.get(field_map.get(tid, tid), []) or []
                # event_f1 buckets by 5-minute window, so an unknown truth time
                # can't participate — drop such events rather than mis-bucket.
                truth_ev = metrics.sanitize_truth_events(truth_ev, require_time=True)
                score = metrics.f1_set(_event_keys(pred_ev), _event_keys(truth_ev))
            elif metric == "smape":
                key = tid.replace("tactical_formation_match", "").strip() or tid
                # maps task id -> stats key
                stat_key = {
                    "possession_pct": "possession",
                    "shots": "shots",
                    "shots_on_target": "shots_on_target",
                    "corners": "corners",
                    "pass_accuracy": "pass_accuracy",
                    "fouls": "fouls",
                    "saves": "saves",
                    "tackles_and_interceptions": "defensive_actions",
                }.get(tid)
                if stat_key:
                    score = _stats_smape(prediction, truth, stat_key)
            elif metric == "kendall_tau":
                score = metrics.kendall_tau(
                    [t["id"] for t in prediction.get("group_standings", []) or []],
                    [t["id"] for t in truth.get("group_standings", []) or []],
                )
            elif metric == "bracket_score":
                score = metrics.bracket_score(
                    prediction.get("bracket", {}),
                    truth.get("bracket", {}),
                )
            elif metric == "brier_multiclass":
                score = metrics.brier_multiclass(
                    prediction.get("champion_probs", {}),
                    truth.get("champion", ""),
                )
            elif metric == "ndcg_at_3":
                score = metrics.ndcg_at_k(
                    [_norm(p.get("player")) for p in prediction.get("top_scorer_probs", []) or []],
                    [_norm(n) for n in truth.get("top_scorers", []) or []],
                    k=3,
                )
        except Exception as e:  # noqa: BLE001
            per_task[tid] = {"score": 0.0, "error": f"{type(e).__name__}: {e}"}
            continue
        per_task[tid] = {"score": float(score)}

    # aggregate by layer
    by_layer: dict[str, float] = {}
    for task in cfg["tasks"]:
        lid = task["layer"]
        contrib = per_task[task["id"]]["score"] * task["weight_in_layer"]
        by_layer[lid] = by_layer.get(lid, 0.0) + contrib

    composite = sum(by_layer.get(lid, 0.0) * w for lid, w in cfg["layer_weights"].items())

    return {"tasks": per_task, "layers": by_layer, "composite": composite}
