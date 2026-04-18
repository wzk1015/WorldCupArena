"""Per-metric scoring primitives. Each returns a float in [0, 100] unless noted.

Reference docs in docs/tech_report.md (§ Metrics).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np


# ----------------------------------------------------------------------
# Probability scores
# ----------------------------------------------------------------------

def brier_3way(pred: dict[str, float], truth: str) -> float:
    """3-class Brier score -> 0..100 (higher better). truth ∈ {home,draw,away}."""
    idx = {"home": 0, "draw": 1, "away": 2}
    y = np.zeros(3)
    y[idx[truth]] = 1.0
    p = np.array([pred.get("home", 0), pred.get("draw", 0), pred.get("away", 0)])
    if p.sum() > 0:
        p = p / p.sum()
    brier = float(np.sum((p - y) ** 2))      # 0 (perfect) .. 2 (worst)
    return max(0.0, 100.0 * (1 - brier / 2))


def brier_binary(p: float, truth: bool) -> float:
    y = 1.0 if truth else 0.0
    p = max(0.0, min(1.0, p))
    return 100.0 * (1 - (p - y) ** 2)


def brier_multiclass(probs: dict[str, float], truth: str) -> float:
    total = sum(probs.values()) or 1.0
    p = {k: v / total for k, v in probs.items()}
    brier = sum((p.get(k, 0) - (1.0 if k == truth else 0.0)) ** 2 for k in set(p) | {truth})
    return max(0.0, 100.0 * (1 - brier / 2))


def rps_score(score_dist: list[dict[str, Any]], actual_score: str) -> float:
    """Ranked Probability Score over {home win, draw, away win} derived from score distribution."""
    agg = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for s in score_dist:
        h, a = _parse_score(s["score"])
        key = "home" if h > a else "away" if a > h else "draw"
        agg[key] += float(s["p"])
    return brier_3way(agg, _result_of(actual_score))


# ----------------------------------------------------------------------
# Regression-style
# ----------------------------------------------------------------------

def mae(pred_value: float, truth_value: float, scale: float = 5.0) -> float:
    err = abs(pred_value - truth_value)
    return 100.0 * max(0.0, 1 - err / scale)


def smape(pred: float, truth: float) -> float:
    denom = (abs(pred) + abs(truth)) / 2
    if denom == 0:
        return 100.0
    return 100.0 * max(0.0, 1 - abs(pred - truth) / denom)


# ----------------------------------------------------------------------
# Set / classification
# ----------------------------------------------------------------------

def f1_set(pred: Iterable[str], truth: Iterable[str]) -> float:
    P, T = set(pred), set(truth)
    if not P and not T:
        return 100.0
    tp = len(P & T)
    precision = tp / len(P) if P else 0
    recall = tp / len(T) if T else 0
    if precision + recall == 0:
        return 0.0
    return 100.0 * 2 * precision * recall / (precision + recall)


def jaccard(pred: Iterable[str], truth: Iterable[str]) -> float:
    P, T = set(pred), set(truth)
    if not P and not T:
        return 100.0
    return 100.0 * len(P & T) / len(P | T)


def exact_match(pred: Any, truth: Any) -> float:
    return 100.0 if pred == truth else 0.0


def top1_accuracy(pred_sorted: Sequence[str], truth: str) -> float:
    return 100.0 if pred_sorted and pred_sorted[0] == truth else 0.0


# ----------------------------------------------------------------------
# Ranking
# ----------------------------------------------------------------------

def ndcg_at_k(pred_ranking: Sequence[str], truth_ranking: Sequence[str], k: int = 3) -> float:
    rel = {name: (len(truth_ranking) - i) for i, name in enumerate(truth_ranking)}
    dcg = sum(rel.get(p, 0) / math.log2(i + 2) for i, p in enumerate(pred_ranking[:k]))
    idcg = sum((len(truth_ranking) - i) / math.log2(i + 2) for i in range(min(k, len(truth_ranking))))
    return 100.0 * dcg / idcg if idcg else 0.0


def kendall_tau(pred_order: Sequence[str], truth_order: Sequence[str]) -> float:
    items = list(dict.fromkeys(list(pred_order) + list(truth_order)))
    rp = {x: i for i, x in enumerate(pred_order)}
    rt = {x: i for i, x in enumerate(truth_order)}
    concordant = discordant = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a not in rp or b not in rp or a not in rt or b not in rt:
                continue
            sp = rp[a] - rp[b]
            st = rt[a] - rt[b]
            if sp * st > 0:
                concordant += 1
            elif sp * st < 0:
                discordant += 1
    total = concordant + discordant
    if total == 0:
        return 0.0
    tau = (concordant - discordant) / total
    return 100.0 * (tau + 1) / 2


# ----------------------------------------------------------------------
# Truth-side sanitization
# ----------------------------------------------------------------------
#
# API-Football and other ingest sources occasionally emit events with nonsense
# time fields (negative minute, null, non-numeric) or missing actors. We only
# sanitize *truth* — per spec we never second-guess model predictions.
#
# Rules:
#   - If the actor field is missing/empty, drop the event (can't match it).
#   - If the time field is invalid (None, non-numeric, negative), strip the
#     time fields so downstream metrics treat the time as "unknown" rather
#     than penalizing the prediction for getting it wrong.

def sanitize_truth_events(
    events: Iterable[dict[str, Any]] | None,
    actor_key: str = "player",
    time_key: str = "minute",
    require_time: bool = False,
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for e in events or []:
        actor = e.get(actor_key)
        if not (isinstance(actor, str) and actor.strip()):
            continue  # unsalvageable — drop
        t = _mid_minute(e.get(time_key))
        if t is None:
            t = _mid_minute(e.get("minute_range"))
        valid_time = t is not None and t >= 0
        if not valid_time and require_time:
            continue  # caller can't handle unknown time — drop the event
        out = dict(e)
        if not valid_time:
            out.pop(time_key, None)
            out.pop("minute_range", None)
        cleaned.append(out)
    return cleaned


# ----------------------------------------------------------------------
# Event matching (goals, subs, cards) with Hungarian bipartite match on time
# ----------------------------------------------------------------------

def hungarian_minute_mae(
    pred_events: list[dict[str, Any]],
    truth_events: list[dict[str, Any]],
    key: str = "player",
    time_key: str = "minute",
    no_match_penalty: float = 30.0,
) -> float:
    from scipy.optimize import linear_sum_assignment  # lazy import

    truth_events = sanitize_truth_events(truth_events, actor_key=key, time_key=time_key)

    if not pred_events and not truth_events:
        return 100.0
    if not pred_events or not truth_events:
        return 0.0

    cost = np.zeros((len(pred_events), len(truth_events)))
    for i, pe in enumerate(pred_events):
        for j, te in enumerate(truth_events):
            same_actor = str(pe.get(key, "")).strip().lower() == str(te.get(key, "")).strip().lower()
            t_pred = _mid_minute(pe.get(time_key) or pe.get("minute_range"))
            t_true = _mid_minute(te.get(time_key) or te.get("minute_range"))
            if t_true is None:
                gap = 0.0                       # truth time is unknown → don't penalize minute
            elif t_pred is None:
                gap = no_match_penalty          # prediction omitted a time we do know
            else:
                gap = abs(t_pred - t_true)
            cost[i, j] = gap + (0 if same_actor else no_match_penalty)
    row_ind, col_ind = linear_sum_assignment(cost)
    matched = cost[row_ind, col_ind]
    n_unmatched = abs(len(pred_events) - len(truth_events))
    avg_cost = (matched.sum() + n_unmatched * no_match_penalty) / max(len(pred_events), len(truth_events))
    return max(0.0, 100.0 - avg_cost)


# ----------------------------------------------------------------------
# Bracket (round-weighted correctness)
# ----------------------------------------------------------------------

def bracket_score(pred_bracket: dict[str, Any], truth_bracket: dict[str, Any]) -> float:
    """pred/truth shape: {round_name: [team_id, ...]}. Weight per round = 2**round_idx."""
    rounds = [
        "R16", "QF", "SF", "FINAL", "CHAMPION",
    ]
    total, earned = 0, 0
    for idx, r in enumerate(rounds):
        w = 2 ** idx
        for t in truth_bracket.get(r, []):
            total += w
            if t in pred_bracket.get(r, []):
                earned += w
    return 100.0 * earned / total if total else 0.0


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _parse_score(s: str) -> tuple[int, int]:
    h, a = s.split("-")
    return int(h), int(a)


def _result_of(s: str) -> str:
    h, a = _parse_score(s)
    return "home" if h > a else "away" if a > h else "draw"


def _mid_minute(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, bool):
            return None  # bool is int subclass — reject explicitly
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip():
            return float(v)
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (float(v[0]) + float(v[1])) / 2
    except (TypeError, ValueError):
        return None
    return None
