"""Post-process exact-score distributions into calibrated football score grids.

LLMs tend to collapse exact-score forecasts onto template scorelines such as
2-1. A pure Poisson replacement has the opposite failure mode: many balanced
matches collapse onto 1-1. This module blends both signals, then calibrates the
aggregate home/draw/away mass back to the model's win_probs.
"""

from __future__ import annotations

import json
import math
from typing import Any


OUTCOMES = ("home", "draw", "away")
SCORE_CALIBRATION_METHOD = "hybrid_poisson_model_v2"
MANDATORY_SCORES = {
    "0-0", "1-1", "2-2",
    "1-0", "0-1", "2-0", "0-2", "2-1", "1-2",
    "3-0", "0-3", "3-1", "1-3", "3-2", "2-3",
}


def _outcome(score: str) -> str | None:
    parts = score.split("-") if score else []
    if len(parts) != 2:
        return None
    try:
        h_goals, a_goals = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    return "home" if h_goals > a_goals else "away" if a_goals > h_goals else "draw"


def _normalize_probs(win_probs: dict[str, Any]) -> dict[str, float]:
    raw = {k: max(0.0, float(win_probs.get(k, 0.0))) for k in OUTCOMES}
    total = sum(raw.values())
    if total <= 0:
        return {"home": 0.38, "draw": 0.27, "away": 0.35}
    return {k: raw[k] / total for k in OUTCOMES}


def _poisson_pmf(lam: float, max_goals: int) -> list[float]:
    return [math.exp(-lam) * (lam ** g) / math.factorial(g) for g in range(max_goals + 1)]


def _grid(lam_home: float, lam_away: float, max_goals: int) -> list[dict[str, Any]]:
    home_p = _poisson_pmf(lam_home, max_goals)
    away_p = _poisson_pmf(lam_away, max_goals)
    rows: list[dict[str, Any]] = []
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = home_p[h] * away_p[a]
            rows.append({"score": f"{h}-{a}", "p": p, "outcome": _outcome(f"{h}-{a}")})
    total = sum(r["p"] for r in rows) or 1.0
    for r in rows:
        r["p"] /= total
    return rows


def _outcome_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = {k: 0.0 for k in OUTCOMES}
    for r in rows:
        outcome = r.get("outcome") or _outcome(str(r.get("score", "")))
        if outcome:
            totals[outcome] += float(r.get("p", 0.0))
    return totals


def _score_dist_totals(score_dist: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    if not score_dist:
        return None, None
    total_p = sum(float(x.get("p", 0.0)) for x in score_dist)
    if total_p <= 0:
        return None, None
    total_goals = 0.0
    goal_diff = 0.0
    for item in score_dist:
        score = str(item.get("score", ""))
        parts = score.split("-")
        if len(parts) != 2:
            continue
        try:
            h_goals, a_goals = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        p = float(item.get("p", 0.0)) / total_p
        total_goals += (h_goals + a_goals) * p
        goal_diff += (h_goals - a_goals) * p
    return total_goals, goal_diff


def _target_total_goals(pred: dict[str, Any], win_probs: dict[str, float]) -> float:
    model_total, _ = _score_dist_totals(pred.get("score_dist") or [])
    # Higher draw probability generally implies a lower-event match. This is a
    # deliberately gentle prior; the model's own score_dist total is blended in
    # when available, but clipped so template-heavy outputs cannot dominate.
    draw_based_total = 2.65 + (0.26 - win_probs["draw"]) * 4.5
    draw_based_total = min(4.0, max(1.7, draw_based_total))
    if model_total is None:
        return draw_based_total
    model_total = min(4.2, max(1.6, model_total))
    return 0.55 * draw_based_total + 0.45 * model_total


def _target_goal_diff(pred: dict[str, Any]) -> float | None:
    value = pred.get("expected_goal_diff")
    if isinstance(value, int | float):
        return float(value)
    _, dist_diff = _score_dist_totals(pred.get("score_dist") or [])
    return dist_diff


def _fit_lambdas(
    win_probs: dict[str, float],
    target_total: float,
    target_diff: float | None,
    max_goals: int,
) -> tuple[float, float, dict[str, float]]:
    best: tuple[float, float, dict[str, float], float] | None = None
    # 0.20..4.50 in 0.05 steps, without numpy dependency.
    values = [round(0.20 + i * 0.05, 2) for i in range(87)]
    for lam_home in values:
        for lam_away in values:
            rows = _grid(lam_home, lam_away, max_goals)
            totals = _outcome_totals(rows)
            outcome_err = sum((totals[k] - win_probs[k]) ** 2 for k in OUTCOMES)
            total_err = (lam_home + lam_away - target_total) ** 2
            diff_err = 0.0 if target_diff is None else (lam_home - lam_away - target_diff) ** 2
            loss = 12.0 * outcome_err + 0.65 * total_err + 0.45 * diff_err
            if best is None or loss < best[3]:
                best = (lam_home, lam_away, totals, loss)
    assert best is not None
    return best[0], best[1], best[2]


def _select_scorelines(
    rows: list[dict[str, Any]],
    win_probs: dict[str, float],
    max_scorelines: int,
    must_keep: set[str] | None = None,
) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda r: float(r["p"]), reverse=True)
    must_keep = must_keep or set()
    selected = {r["score"]: dict(r) for r in sorted_rows[:max_scorelines]}
    for score in must_keep:
        found = next((r for r in sorted_rows if r["score"] == score), None)
        if found:
            selected[score] = dict(found)

    # Ensure every non-trivial outcome bucket has at least one representative so
    # the later outcome-level calibration can preserve win_probs.
    for outcome in OUTCOMES:
        if win_probs[outcome] < 0.01:
            continue
        if any(r.get("outcome") == outcome for r in selected.values()):
            continue
        candidate = next(r for r in sorted_rows if r.get("outcome") == outcome)
        removable = [r for r in selected.values() if r["score"] not in must_keep]
        lowest = min(removable or selected.values(), key=lambda r: float(r["p"]))
        selected.pop(str(lowest["score"]), None)
        selected[str(candidate["score"])] = dict(candidate)

    while len(selected) > max_scorelines:
        removable = [r for r in selected.values() if r["score"] not in must_keep]
        lowest = min(removable or selected.values(), key=lambda r: float(r["p"]))
        selected.pop(str(lowest["score"]), None)

    return list(selected.values())


def _model_score_probs(pred: dict[str, Any]) -> dict[str, float]:
    score_dist = pred.get("score_dist") or []
    raw: dict[str, float] = {}
    for item in score_dist:
        score = str(item.get("score", ""))
        if _outcome(score):
            raw[score] = raw.get(score, 0.0) + max(0.0, float(item.get("p", 0.0)))
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {score: p / total for score, p in raw.items()}


def _blend_rows(
    poisson_rows: list[dict[str, Any]],
    model_probs: dict[str, float],
    *,
    model_weight: float,
) -> list[dict[str, Any]]:
    by_score = {str(r["score"]): r for r in poisson_rows}
    poisson_top = {
        str(r["score"])
        for r in sorted(poisson_rows, key=lambda r: float(r["p"]), reverse=True)[:24]
    }
    model_top = {
        score
        for score, _ in sorted(model_probs.items(), key=lambda item: item[1], reverse=True)[:16]
    }
    candidates = {s for s in poisson_top | model_top | MANDATORY_SCORES if s in by_score}
    poisson_total = sum(float(by_score[s]["p"]) for s in candidates) or 1.0
    model_total = sum(model_probs.get(s, 0.0) for s in candidates) or 1.0
    rows: list[dict[str, Any]] = []
    for score in candidates:
        poisson_p = float(by_score[score]["p"]) / poisson_total
        model_p = model_probs.get(score, 0.0) / model_total
        p = model_weight * model_p + (1.0 - model_weight) * poisson_p
        rows.append({"score": score, "p": p, "outcome": _outcome(score)})
    total = sum(float(r["p"]) for r in rows) or 1.0
    for row in rows:
        row["p"] = float(row["p"]) / total
    return rows


def _rake_to_outcomes(
    rows: list[dict[str, Any]],
    win_probs: dict[str, float],
) -> list[dict[str, Any]]:
    totals = _outcome_totals(rows)
    adjusted: list[dict[str, Any]] = []
    for row in rows:
        outcome = row.get("outcome")
        if not outcome or totals[outcome] <= 0:
            continue
        new_row = dict(row)
        new_row["p"] = float(row["p"]) * win_probs[outcome] / totals[outcome]
        adjusted.append(new_row)
    total = sum(float(r["p"]) for r in adjusted) or 1.0
    for row in adjusted:
        row["p"] = float(row["p"]) / total
    return adjusted


def _apply_top_score_policy(
    rows: list[dict[str, Any]],
    win_probs: dict[str, float],
    *,
    model_top_score: str | None,
    favorite_margin: float,
) -> list[dict[str, Any]]:
    """Avoid pure-Poisson 1-1 collapse when there is a clear non-draw favorite.

    We keep aggregate outcome mass unchanged by moving probability only within
    the favorite outcome bucket.
    """
    if not rows:
        return rows
    favorite = max(OUTCOMES, key=lambda outcome: win_probs[outcome])
    if favorite == "draw" or win_probs[favorite] - win_probs["draw"] < favorite_margin:
        return rows

    current_top = max(rows, key=lambda row: float(row["p"]))
    if current_top.get("outcome") == favorite:
        return rows

    preferred_score = model_top_score if model_top_score and _outcome(model_top_score) == favorite else None
    preferred = next((r for r in rows if r["score"] == preferred_score), None) if preferred_score else None
    if preferred is None:
        preferred = max((r for r in rows if r.get("outcome") == favorite), key=lambda row: float(row["p"]), default=None)
    if preferred is None:
        return rows

    # Leave enough headroom to survive 3-decimal rounding later.
    needed = float(current_top["p"]) + 0.006 - float(preferred["p"])
    if needed <= 0:
        return rows

    out = [dict(r) for r in rows]
    target = next(r for r in out if r["score"] == preferred["score"])
    donors = [
        r for r in sorted(out, key=lambda row: float(row["p"]), reverse=True)
        if r.get("outcome") == favorite and r["score"] != target["score"]
    ]
    for donor in donors:
        if needed <= 0:
            break
        available = max(0.0, float(donor["p"]) - 0.001)
        take = min(available, needed)
        donor["p"] = float(donor["p"]) - take
        target["p"] = float(target["p"]) + take
        needed -= take
    return out


def _round_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda r: float(r["p"]), reverse=True)
    out = [{"score": str(r["score"]), "p": round(float(r["p"]), 3)} for r in rows]
    diff = round(1.0 - sum(r["p"] for r in out), 3)
    if out and diff:
        out[0]["p"] = round(max(0.0, out[0]["p"] + diff), 3)
    return out


def calibrate_score_prediction(
    pred: dict[str, Any],
    *,
    max_goals: int = 7,
    max_scorelines: int = 20,
    model_weight: float = 0.62,
    favorite_margin: float = 0.15,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a prediction with calibrated score_dist/most_likely_score.

    The returned metadata is intended for the outer prediction record, not the
    schema-constrained prediction object.
    """
    out = json.loads(json.dumps(pred))
    win_probs = _normalize_probs(out.get("win_probs") or {})
    target_total = _target_total_goals(out, win_probs)
    target_diff = _target_goal_diff(out)
    lam_home, lam_away, fitted_outcomes = _fit_lambdas(
        win_probs,
        target_total=target_total,
        target_diff=target_diff,
        max_goals=max_goals,
    )
    poisson_rows = _grid(lam_home, lam_away, max_goals)
    model_probs = _model_score_probs(out)
    rows = _blend_rows(poisson_rows, model_probs, model_weight=model_weight)
    model_top_score = str(out.get("most_likely_score", "")) or None
    must_keep = {model_top_score} if model_top_score and _outcome(model_top_score) else set()
    selected = _select_scorelines(rows, win_probs, max_scorelines, must_keep=must_keep)
    adjusted = _rake_to_outcomes(selected, win_probs)
    adjusted = _apply_top_score_policy(
        adjusted,
        win_probs,
        model_top_score=model_top_score,
        favorite_margin=favorite_margin,
    )
    score_dist = _round_distribution(adjusted)

    before = {
        "most_likely_score": out.get("most_likely_score"),
        "score_dist_head": (out.get("score_dist") or [])[:5],
    }
    out["win_probs"] = {k: round(v, 3) for k, v in win_probs.items()}
    out["score_dist"] = score_dist
    out["most_likely_score"] = score_dist[0]["score"] if score_dist else out.get("most_likely_score")
    out["expected_goal_diff"] = round(lam_home - lam_away, 3)

    metadata = {
        "applied": True,
        "method": SCORE_CALIBRATION_METHOD,
        "model_weight": round(model_weight, 3),
        "favorite_margin": round(favorite_margin, 3),
        "lambda_home": round(lam_home, 3),
        "lambda_away": round(lam_away, 3),
        "target_total_goals": round(target_total, 3),
        "target_goal_diff": round(target_diff, 3) if target_diff is not None else None,
        "fitted_outcomes": {k: round(v, 3) for k, v in fitted_outcomes.items()},
        "before": before,
        "after": {
            "most_likely_score": out.get("most_likely_score"),
            "score_dist_head": score_dist[:5],
        },
    }
    return out, metadata
