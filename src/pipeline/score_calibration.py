"""Post-process exact-score distributions into calibrated football score grids.

LLMs tend to produce inconsistent headline result/score forecasts when asked
for too many probability tables at once. This module turns model-owned
high-level parameters (win_probs, expected_total_goals, expected_goal_diff, and
an optional headline score hint) into a deterministic exact-score grid whose
headline score always matches the model's highest-probability 3-way outcome.
"""

from __future__ import annotations

import json
import math
from typing import Any

from .prediction_derivatives import (
    OUTCOMES,
    attach_score_derived_fields,
    best_win_outcome,
    derive_win_probs_from_score_dist,
    normalize_win_probs,
    score_outcome,
)


SCORE_CALIBRATION_METHOD = "winprob_poisson_generator_v1"
OVER_UNDER_KEYS = ("over_1_5", "over_2_5", "over_3_5", "over_4_5")
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


def _score_dist_win_probs(score_dist: list[dict[str, Any]]) -> dict[str, float]:
    derived = derive_win_probs_from_score_dist(score_dist)
    if not derived:
        return {"home": 0.38, "draw": 0.27, "away": 0.35}
    return {outcome: float(derived[outcome]) for outcome in OUTCOMES}


def _poisson_pmf(lam: float, max_goals: int) -> list[float]:
    return [math.exp(-lam) * (lam ** g) / math.factorial(g) for g in range(max_goals + 1)]


def _poisson_over_probs(total_lambda: float, max_goals: int = 16) -> dict[str, float]:
    pmf = _poisson_pmf(max(0.01, total_lambda), max_goals)
    total = sum(pmf) or 1.0
    pmf = [p / total for p in pmf]
    return {
        "over_1_5": sum(pmf[2:]),
        "over_2_5": sum(pmf[3:]),
        "over_3_5": sum(pmf[4:]),
        "over_4_5": sum(pmf[5:]),
    }


def _profile_from_total(total_lambda: float) -> str:
    if total_lambda >= 3.55:
        return "chaos"
    if total_lambda >= 3.05:
        return "open"
    if total_lambda >= 2.25:
        return "normal"
    return "low_event"


def _coherent_profile(profile: Any, total_lambda: float) -> str:
    derived = _profile_from_total(total_lambda)
    if profile == "low_event" and total_lambda > 2.6:
        return derived
    if profile == "chaos" and total_lambda < 3.2:
        return derived
    if profile in {"low_event", "normal", "open", "chaos"}:
        return str(profile)
    return derived


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


def _score_dist_over_probs(score_dist: list[dict[str, Any]]) -> dict[str, float]:
    total_p = sum(float(x.get("p", 0.0)) for x in score_dist or [])
    if total_p <= 0:
        return {key: 0.0 for key in OVER_UNDER_KEYS}
    out = {key: 0.0 for key in OVER_UNDER_KEYS}
    for item in score_dist:
        score = str(item.get("score", ""))
        parts = score.split("-")
        if len(parts) != 2:
            continue
        try:
            total_goals = int(parts[0]) + int(parts[1])
        except ValueError:
            continue
        p = float(item.get("p", 0.0)) / total_p
        if total_goals >= 2:
            out["over_1_5"] += p
        if total_goals >= 3:
            out["over_2_5"] += p
        if total_goals >= 4:
            out["over_3_5"] += p
        if total_goals >= 5:
            out["over_4_5"] += p
    return out


def _target_total_goals(pred: dict[str, Any], win_probs: dict[str, float]) -> float:
    model_total, _ = _score_dist_totals(pred.get("score_dist") or [])
    # Higher draw probability generally implies a lower-event match. This is a
    # deliberately gentle prior, not a cap: open knockout/game-state evidence
    # should come through the model's explicit total-goals estimate.
    draw_based_total = 2.65 + (0.26 - win_probs["draw"]) * 4.5
    draw_based_total = min(4.6, max(1.6, draw_based_total))

    expected_total = pred.get("expected_total_goals")
    if isinstance(expected_total, int | float):
        expected_total = min(6.0, max(1.0, float(expected_total)))
    else:
        expected_total = None

    over_3_5 = None
    over_4_5 = None
    ou = pred.get("over_under_probs") or {}
    if isinstance(ou.get("over_3_5"), int | float):
        over_3_5 = float(ou["over_3_5"])
    if isinstance(ou.get("over_4_5"), int | float):
        over_4_5 = float(ou["over_4_5"])
    score_overs = _score_dist_over_probs(pred.get("score_dist") or [])
    over_3_5 = max(over_3_5 or 0.0, score_overs["over_3_5"])
    over_4_5 = max(over_4_5 or 0.0, score_overs["over_4_5"])

    if model_total is None and expected_total is None:
        return draw_based_total

    if model_total is not None:
        model_total = min(5.5, max(1.3, model_total))

    if expected_total is not None and model_total is not None:
        target = 0.72 * expected_total + 0.18 * model_total + 0.10 * draw_based_total
    elif expected_total is not None:
        target = 0.85 * expected_total + 0.15 * draw_based_total
    else:
        target = 0.35 * draw_based_total + 0.65 * float(model_total)

    # If the model explicitly prices a high-event match, make sure a high draw
    # probability does not silently drag the grid back toward 1-1/2-1 templates.
    if over_3_5 >= 0.40:
        target = max(target, 3.35)
    if over_3_5 >= 0.30:
        target = max(target, 3.05)
    if over_4_5 >= 0.22:
        target = max(target, 3.70)
    profile = pred.get("match_profile")
    if profile == "open":
        target = max(target, 3.05)
    elif profile == "chaos":
        target = max(target, 3.55)
    return min(6.0, max(1.0, target))


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
    # the later outcome-level calibration can preserve score-derived outcome mass.
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


def _apply_high_event_top_policy(
    rows: list[dict[str, Any]],
    *,
    profile: str,
) -> list[dict[str, Any]]:
    """Promote plausible 4+ goal scorelines in open/chaos matches.

    Probability only moves within the selected scoreline's outcome bucket, so
    aggregate home/draw/away calibration remains intact.
    """
    if profile not in {"open", "chaos"} or not rows:
        return rows

    current_top = max(rows, key=lambda row: float(row["p"]))
    try:
        high_candidates = [
            row for row in rows
            if sum(int(part) for part in str(row.get("score", "0-0")).split("-")) >= 4
        ]
    except ValueError:
        high_candidates = []
    if not high_candidates:
        return rows

    target = max(high_candidates, key=lambda row: float(row["p"]))
    ratio = float(target["p"]) / (float(current_top["p"]) or 1.0)
    min_ratio = 0.62 if profile == "chaos" else 0.70
    if ratio < min_ratio:
        return rows

    out = [dict(r) for r in rows]
    target_out = next(r for r in out if r["score"] == target["score"])
    needed = float(current_top["p"]) + 0.006 - float(target_out["p"])
    if needed <= 0:
        return out

    donors = [
        r for r in sorted(out, key=lambda row: float(row["p"]), reverse=True)
        if r.get("outcome") == target_out.get("outcome") and r["score"] != target_out["score"]
    ]
    for donor in donors:
        if needed <= 0:
            break
        available = max(0.0, float(donor["p"]) - 0.001)
        take = min(available, needed)
        donor["p"] = float(donor["p"]) - take
        target_out["p"] = float(target_out["p"]) + take
        needed -= take
    return out


def _apply_forced_outcome_top_policy(
    rows: list[dict[str, Any]],
    win_probs: dict[str, float],
    *,
    score_hint: str | None,
) -> list[dict[str, Any]]:
    """Force the headline exact score to live in argmax(win_probs)' bucket."""
    if not rows:
        return rows
    target_outcome = best_win_outcome(win_probs)
    if target_outcome is None:
        return rows

    current_top = max(rows, key=lambda row: float(row["p"]))
    if current_top.get("outcome") == target_outcome:
        return rows

    preferred = None
    if score_hint and score_outcome(score_hint) == target_outcome:
        preferred = next((row for row in rows if row["score"] == score_hint), None)
    if preferred is None:
        preferred = max((row for row in rows if row.get("outcome") == target_outcome), key=lambda row: float(row["p"]), default=None)
    if preferred is None:
        return rows

    out = [dict(row) for row in rows]
    target = next(row for row in out if row["score"] == preferred["score"])
    current_top_p = max(float(row["p"]) for row in out if row["score"] != target["score"])
    needed = current_top_p + 0.006 - float(target["p"])
    if needed <= 0:
        return out

    donors = [
        row for row in sorted(out, key=lambda item: float(item["p"]), reverse=True)
        if row.get("outcome") == target_outcome and row["score"] != target["score"]
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
        if diff > 0:
            out[0]["p"] = round(out[0]["p"] + diff, 3)
        else:
            target = next((row for row in reversed(out) if row["p"] + diff >= 0), out[-1])
            target["p"] = round(max(0.0, target["p"] + diff), 3)
    return sorted(out, key=lambda row: float(row["p"]), reverse=True)


def calibrate_score_prediction(
    pred: dict[str, Any],
    *,
    max_goals: int = 7,
    max_scorelines: int = 20,
    model_weight: float = 0.62,
    favorite_margin: float = 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a prediction with generated score_dist/most_likely_score.

    The returned metadata is intended for the outer prediction record, not the
    model-schema-constrained object.
    """
    out = json.loads(json.dumps(pred))
    win_probs = normalize_win_probs(out.get("win_probs")) or _score_dist_win_probs(out.get("score_dist") or [])
    if not win_probs:
        win_probs = {"home": 0.38, "draw": 0.27, "away": 0.35}
    out["win_probs"] = win_probs
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
    effective_model_weight = model_weight if model_probs else 0.0
    rows = _blend_rows(poisson_rows, model_probs, model_weight=effective_model_weight)
    score_hint = str(out.get("headline_score") or out.get("most_likely_score") or "") or None
    favored_outcome = best_win_outcome(win_probs)
    model_top_score = score_hint if score_hint and _outcome(score_hint) == favored_outcome else None
    must_keep = {model_top_score} if model_top_score else set()
    selected = _select_scorelines(rows, win_probs, max_scorelines, must_keep=must_keep)
    adjusted = _rake_to_outcomes(selected, win_probs)
    adjusted = _apply_high_event_top_policy(
        adjusted,
        profile=str(out.get("match_profile") or _profile_from_total(target_total)),
    )
    adjusted = _apply_forced_outcome_top_policy(
        adjusted,
        win_probs,
        score_hint=model_top_score,
    )
    score_dist = _round_distribution(adjusted)

    before = {
        "headline_score": out.get("headline_score"),
        "most_likely_score": out.get("most_likely_score"),
        "win_probs": out.get("win_probs"),
        "score_dist_head": (out.get("score_dist") or [])[:5],
    }
    out["score_dist"] = score_dist
    out["most_likely_score"] = score_dist[0]["score"] if score_dist else out.get("headline_score")
    out["match_profile"] = _coherent_profile(out.get("match_profile"), lam_home + lam_away)
    out["expected_total_goals"] = round(lam_home + lam_away, 3)
    out["expected_goal_diff"] = round(lam_home - lam_away, 3)
    out["over_under_probs"] = {
        key: round(value, 3)
        for key, value in _score_dist_over_probs(score_dist).items()
    }

    metadata = {
        "applied": True,
        "method": SCORE_CALIBRATION_METHOD,
        "model_weight": round(effective_model_weight, 3),
        "favorite_margin": round(favorite_margin, 3),
        "lambda_home": round(lam_home, 3),
        "lambda_away": round(lam_away, 3),
        "target_total_goals": round(target_total, 3),
        "target_goal_diff": round(target_diff, 3) if target_diff is not None else None,
        "target_outcome_probs": win_probs,
        "forced_headline_outcome": favored_outcome,
        "score_hint_used": model_top_score,
        "fitted_outcomes": {k: round(v, 3) for k, v in fitted_outcomes.items()},
        "before": before,
        "after": {
            "most_likely_score": out.get("most_likely_score"),
            "score_dist_head": score_dist[:5],
        },
    }
    return out, metadata


def _candidate_scores(
    pred: dict[str, Any],
    *,
    min_ratio: float = 0.65,
    max_rank: int = 10,
) -> list[dict[str, Any]]:
    rows = sorted(pred.get("score_dist") or [], key=lambda row: float(row.get("p", 0)), reverse=True)
    if not rows:
        return []
    top_p = float(rows[0].get("p", 0))
    candidates: list[dict[str, Any]] = []
    for rank, row in enumerate(rows[:max_rank], 1):
        score = str(row.get("score", ""))
        outcome = _outcome(score)
        if not outcome:
            continue
        p = float(row.get("p", 0))
        if top_p > 0 and p < top_p * min_ratio:
            continue
        total = sum(int(part) for part in score.split("-"))
        candidates.append({"score": score, "p": p, "rank": rank, "outcome": outcome, "total": total})
    return candidates


def _round_rows(rows: list[dict[str, Any]], top_score: str) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda row: float(row.get("p", 0)), reverse=True)
    out = [{"score": str(row["score"]), "p": round(float(row["p"]), 3)} for row in rows]
    diff = round(1.0 - sum(row["p"] for row in out), 3)
    target = next((row for row in out if row["score"] == top_score), None)
    if target is not None and diff:
        target["p"] = round(max(0.0, target["p"] + diff), 3)
    return sorted(out, key=lambda row: float(row["p"]), reverse=True)


def _align_prediction_to_score(pred: dict[str, Any], score: str) -> dict[str, Any]:
    """Make prediction fields coherent around a chosen exact score.

    The chosen score must already be a plausible candidate from the model's own
    score_dist. We preserve within-outcome ordering as much as possible, then
    rake outcome totals so derived win_probs, score_dist, and most_likely_score
    agree.
    """
    out = json.loads(json.dumps(pred))
    rows = [
        {"score": str(row.get("score")), "p": max(0.0, float(row.get("p", 0))), "outcome": _outcome(str(row.get("score", "")))}
        for row in out.get("score_dist") or []
    ]
    rows = [row for row in rows if row["outcome"]]
    target = next((row for row in rows if row["score"] == score), None)
    target_outcome = _outcome(score)
    if target is None or target_outcome is None:
        return out

    total = sum(row["p"] for row in rows) or 1.0
    for row in rows:
        row["p"] /= total

    desired = _outcome_totals(rows)
    max_other = max(desired[outcome] for outcome in OUTCOMES if outcome != target_outcome)
    if desired[target_outcome] <= max_other:
        needed = (max_other + 0.001) - desired[target_outcome]
        donors = [outcome for outcome in OUTCOMES if outcome != target_outcome and desired[outcome] > 0]
        donor_total = sum(desired[outcome] for outcome in donors) or 1.0
        for outcome in donors:
            take = min(desired[outcome] - 0.001, needed * desired[outcome] / donor_total)
            if take > 0:
                desired[outcome] -= take
                desired[target_outcome] += take

    current = _outcome_totals(rows)
    for row in rows:
        outcome = row["outcome"]
        if current[outcome] > 0:
            row["p"] *= desired[outcome] / current[outcome]

    target = next(row for row in rows if row["score"] == score)
    top_p = max(float(row["p"]) for row in rows)
    needed = top_p + 0.006 - float(target["p"])
    if needed > 0:
        donors = [
            row for row in sorted(rows, key=lambda item: float(item["p"]), reverse=True)
            if row["outcome"] == target_outcome and row["score"] != score
        ]
        for donor in donors:
            if needed <= 0:
                break
            available = max(0.0, float(donor["p"]) - 0.001)
            take = min(available, needed)
            donor["p"] -= take
            target["p"] += take
            needed -= take

    rounded = _round_rows(rows, score)
    expected_total = 0.0
    over_under = {key: 0.0 for key in OVER_UNDER_KEYS}
    for row in rounded:
        try:
            total_goals = sum(int(part) for part in row["score"].split("-"))
        except ValueError:
            continue
        p = float(row["p"])
        expected_total += total_goals * p
        if total_goals >= 2:
            over_under["over_1_5"] += p
        if total_goals >= 3:
            over_under["over_2_5"] += p
        if total_goals >= 4:
            over_under["over_3_5"] += p
        if total_goals >= 5:
            over_under["over_4_5"] += p
    out["score_dist"] = rounded
    out["most_likely_score"] = score
    out["match_profile"] = _coherent_profile(out.get("match_profile"), expected_total)
    out["expected_total_goals"] = round(expected_total, 3)
    out["over_under_probs"] = {key: round(value, 3) for key, value in over_under.items()}
    return attach_score_derived_fields(out)


def diversify_prediction_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Diversify final predictions coherently across models for one fixture.

    This does not invent arbitrary scores. Each final score is chosen from that
    model's own near-top score_dist candidates, then the prediction object is
    made internally consistent. The previous prediction is kept in
    pre_diversity_prediction for auditability.
    """
    if len(records) < 2:
        return records

    used_scores: set[str] = set()
    used_outcomes = {outcome: 0 for outcome in OUTCOMES}
    any_draw = False
    any_high = False
    out_records: list[dict[str, Any]] = []

    for record in records:
        pred = record.get("pre_diversity_prediction") or record.get("prediction") or {}
        candidates = _candidate_scores(pred)
        if not candidates:
            out_records.append(record)
            continue

        wp = pred.get("win_probs") or derive_win_probs_from_score_dist(pred.get("score_dist") or [])
        draw_p = float(wp.get("draw", 0))
        over_3_5 = sum(
            float(row.get("p", 0))
            for row in pred.get("score_dist") or []
            if sum(int(part) for part in str(row.get("score", "0-0")).split("-")) >= 4
        )
        top_p = candidates[0]["p"] or 1.0

        def utility(candidate: dict[str, Any]) -> tuple[float, float]:
            value = candidate["p"] / top_p
            if candidate["score"] in used_scores:
                value -= 1.00
            value -= 0.08 * used_outcomes[candidate["outcome"]]
            if not any_draw and candidate["outcome"] == "draw" and draw_p >= 0.22:
                value += 0.22
            if not any_high and candidate["total"] >= 4 and over_3_5 >= 0.18:
                value += 0.14
            return (value, candidate["p"])

        choice = max(candidates, key=utility)
        new_record = json.loads(json.dumps(record))
        if "pre_diversity_prediction" not in new_record:
            new_record["pre_diversity_prediction"] = json.loads(json.dumps(pred))
        new_record["prediction"] = _align_prediction_to_score(pred, choice["score"])
        new_record["fixture_diversification"] = {
            "applied": True,
            "method": "near_top_coherent_diversity_v1",
            "chosen_score": choice["score"],
            "chosen_rank": choice["rank"],
            "chosen_probability_before": round(choice["p"], 3),
            "candidate_scores": [
                {"score": c["score"], "p": round(c["p"], 3), "rank": c["rank"], "outcome": c["outcome"]}
                for c in candidates
            ],
        }
        used_scores.add(choice["score"])
        used_outcomes[choice["outcome"]] += 1
        any_draw = any_draw or choice["outcome"] == "draw"
        any_high = any_high or choice["total"] >= 4
        out_records.append(new_record)

    return out_records
