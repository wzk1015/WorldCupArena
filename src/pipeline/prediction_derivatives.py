"""Helpers for model-owned outcome probabilities and generated score fields."""

from __future__ import annotations

import json
from typing import Any

OUTCOMES = ("home", "draw", "away")


def score_outcome(score: str | None) -> str | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        home_goals, away_goals = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def score_total(score: str | None) -> int | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) + int(parts[1])
    except ValueError:
        return None


def _round_probs(raw: dict[str, float], *, precision: int = 3) -> dict[str, float]:
    rounded = {k: round(max(0.0, raw.get(k, 0.0)), precision) for k in OUTCOMES}
    diff = round(1.0 - sum(rounded.values()), precision)
    if diff:
        target = max(OUTCOMES, key=lambda outcome: raw.get(outcome, 0.0))
        rounded[target] = round(max(0.0, rounded[target] + diff), precision)
    return rounded


def normalize_win_probs(
    win_probs: dict[str, Any] | None,
    *,
    precision: int = 3,
) -> dict[str, float]:
    raw: dict[str, float] = {}
    for outcome in OUTCOMES:
        try:
            raw[outcome] = max(0.0, float((win_probs or {}).get(outcome, 0.0)))
        except (TypeError, ValueError):
            raw[outcome] = 0.0
    total = sum(raw.values())
    if total <= 0:
        return {}
    normalized = {outcome: raw[outcome] / total for outcome in OUTCOMES}
    return _round_probs(normalized, precision=precision)


def best_win_outcome(win_probs: dict[str, Any] | None) -> str | None:
    normalized = normalize_win_probs(win_probs)
    if not normalized:
        return None
    return max(OUTCOMES, key=lambda outcome: normalized[outcome])


def derive_win_probs_from_score_dist(
    score_dist: list[dict[str, Any]] | None,
    *,
    precision: int = 3,
) -> dict[str, float]:
    totals = {outcome: 0.0 for outcome in OUTCOMES}
    total_p = 0.0
    for item in score_dist or []:
        outcome = score_outcome(str(item.get("score", "")))
        if outcome is None:
            continue
        try:
            p = max(0.0, float(item.get("p", 0.0)))
        except (TypeError, ValueError):
            continue
        totals[outcome] += p
        total_p += p
    if total_p <= 0:
        return {}
    raw = {outcome: totals[outcome] / total_p for outcome in OUTCOMES}
    return _round_probs(raw, precision=precision)


def derive_most_likely_score(score_dist: list[dict[str, Any]] | None) -> str | None:
    best_score: str | None = None
    best_p: float | None = None
    for item in score_dist or []:
        score = str(item.get("score", ""))
        if score_outcome(score) is None:
            continue
        try:
            p = float(item.get("p", 0.0))
        except (TypeError, ValueError):
            continue
        if best_p is None or p > best_p:
            best_score = score
            best_p = p
    return best_score


def attach_score_derived_fields(pred: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with missing score-derived fields filled from score_dist.

    This is retained for backwards compatibility with historical predictions.
    New predictions own `win_probs`; the pipeline generates `score_dist`,
    `most_likely_score`, and `over_under_probs` from model-owned parameters.
    """
    out = json.loads(json.dumps(pred))
    score_dist = out.get("score_dist") or []
    if "win_probs" not in out:
        win_probs = derive_win_probs_from_score_dist(score_dist)
        if win_probs:
            out["win_probs"] = win_probs
    else:
        win_probs = normalize_win_probs(out.get("win_probs"))
        if win_probs:
            out["win_probs"] = win_probs
    if "most_likely_score" not in out:
        most_likely = derive_most_likely_score(score_dist)
        if most_likely:
            out["most_likely_score"] = most_likely
    return out


def attach_score_dist_derived_win_probs(pred: dict[str, Any]) -> dict[str, Any]:
    """Legacy helper: force win_probs/most_likely_score from score_dist."""
    out = json.loads(json.dumps(pred))
    win_probs = derive_win_probs_from_score_dist(out.get("score_dist") or [])
    if win_probs:
        out["win_probs"] = win_probs
    else:
        out.pop("win_probs", None)
    most_likely = derive_most_likely_score(out.get("score_dist") or [])
    if most_likely:
        out["most_likely_score"] = most_likely
    else:
        out.pop("most_likely_score", None)
    return out


def strip_generated_score_fields(pred: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(pred))
    out.pop("score_dist", None)
    out.pop("most_likely_score", None)
    out.pop("over_under_probs", None)
    return out


# Backwards-compatible import name used by older pipeline code.
strip_score_derived_fields = strip_generated_score_fields
