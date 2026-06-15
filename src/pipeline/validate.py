"""Comprehensive format validation with retry.

The grader assumes well-formed, schema-compliant JSON. This module enforces that
contract at prediction time so we don't discover missing fields only when trying
to score — at which point the match is already over and we can't re-query.

Validation layers:
    1. JSON parseability (handled by runner, but we re-parse to be safe).
    2. JSON-schema conformance (required fields, types, enums, patterns).
    3. Semantic checks the schema can't express:
         - model win_probs sum ≈ 1
         - generated score_dist p values sum ≈ 1
         - predicted_result, headline score outcome, and argmax(win_probs) match
         - explicit goal events do not contradict headline_score
         - expected_total_goals and generated over/under probabilities match score_dist
         - stats contains all 8 required keys
         - lineups.*.starting has exactly 11 entries
         - reasoning fields are complete and substantive
         - `setting` field matches the invocation
         - `fixture_id` field matches
         - `submitted_at` is ISO-8601 UTC

If any check fails, `validate_or_repair` invokes the runner again with a
structured error message and asks for a corrected JSON — up to `max_retries`
times. Each retry only asks for a patch of the violating fields, to keep
token cost low.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .prediction_derivatives import (
    best_win_outcome,
    derive_win_probs_from_score_dist,
    normalize_win_probs,
    score_outcome,
    score_total,
    strip_generated_score_fields,
)
from .score_calibration import calibrate_score_prediction

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "prediction.schema.json"

REQUIRED_REASONING_FIELDS: dict[str, int] = {
    "overall": 700,
    "market_odds": 180,
    "lineup_analysis": 500,
    "tactical_analysis": 450,
    "h2h_recent_form": 300,
    "player_matchups": 450,
    "injuries_availability": 220,
    "upset_draw_blowout_cases": 350,
    "score_result_rationale": 220,
    "t1_result": 120,
    "t2_player": 180,
    "t3_events": 150,
    "t4_stats": 150,
}


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def add(self, msg: str) -> None:
        self.errors.append(msg)

    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        return "\n".join(f"- {e}" for e in self.errors)


def _validate_schema(pred: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text())
    v = Draft202012Validator(schema)
    schema_pred = strip_generated_score_fields(pred)
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in v.iter_errors(schema_pred)]


def _score_parts(score: object) -> dict[str, int] | None:
    parts = str(score or "").split("-")
    if len(parts) != 2:
        return None
    try:
        return {"home": int(parts[0]), "away": int(parts[1])}
    except ValueError:
        return None


def _opposite_side(side: object) -> str | None:
    if side == "home":
        return "away"
    if side == "away":
        return "home"
    return None


def _validate_goal_event_story(pred: dict[str, Any]) -> list[str]:
    """Catch only hard contradictions; probabilistic scorer lists may be longer."""
    errs: list[str] = []
    target = _score_parts(pred.get("headline_score"))
    if not target:
        return errs

    possible = {"home": 0, "away": 0}
    hard = {"home": 0, "away": 0}

    for scorer in pred.get("scorers") or []:
        side = scorer.get("team")
        if side in possible:
            possible[side] += 1

    for pen in pred.get("penalties") or []:
        if pen.get("outcome") != "scored":
            continue
        side = pen.get("team")
        if side in hard:
            hard[side] += 1
            possible[side] += 1

    for own_goal in pred.get("own_goals") or []:
        credited = _opposite_side(own_goal.get("team"))
        if credited in hard:
            hard[credited] += 1
            possible[credited] += 1

    for side in ("home", "away"):
        if hard[side] > target[side]:
            errs.append(
                f"goal timeline: explicit scored penalties/own goals credit {hard[side]} {side} goals "
                f"but headline_score has {target[side]}"
            )
        if target[side] > 0 and possible[side] == 0:
            errs.append(
                f"goal timeline: headline_score has {target[side]} {side} goals "
                "but no scorer, scored penalty, or credited own goal is available"
            )
    return errs


def _validate_semantics(
    pred: dict[str, Any],
    *,
    fixture_id: str,
    setting_id: str,
    tol: float = 0.01,
) -> list[str]:
    errs: list[str] = []

    if pred.get("fixture_id") != fixture_id:
        errs.append(f"fixture_id mismatch: expected {fixture_id}, got {pred.get('fixture_id')}")
    if pred.get("setting") != setting_id:
        errs.append(f"setting mismatch: expected {setting_id}, got {pred.get('setting')}")

    wp = normalize_win_probs(pred.get("win_probs"))
    if not wp:
        errs.append("win_probs is missing or cannot be normalized")
    else:
        s = sum(float(wp.get(k, 0)) for k in ("home", "draw", "away"))
        if abs(s - 1.0) > tol:
            errs.append(f"win_probs sum={s:.4f} not within {tol} of 1")

    favorite = best_win_outcome(wp)
    headline_score = pred.get("headline_score")
    headline_outcome = None
    if headline_score and favorite:
        headline_outcome = score_outcome(str(headline_score))
        if headline_outcome != favorite:
            errs.append(
                f"headline_score outcome '{headline_outcome}' does not match "
                f"highest win_probs bucket '{favorite}'"
            )
    predicted_result = pred.get("predicted_result")
    if predicted_result not in {"home", "draw", "away"}:
        errs.append(f"predicted_result must be one of home/draw/away, got {predicted_result!r}")
    else:
        if headline_outcome and predicted_result != headline_outcome:
            errs.append(
                f"predicted_result '{predicted_result}' does not match headline_score outcome "
                f"'{headline_outcome}'"
            )
        if favorite and predicted_result != favorite:
            errs.append(
                f"predicted_result '{predicted_result}' does not match highest win_probs bucket "
                f"'{favorite}'"
            )

    errs.extend(_validate_goal_event_story(pred))

    sd = pred.get("score_dist") or []
    if not sd:
        errs.append("score_dist is empty")
    else:
        p_sum = sum(float(x.get("p", 0)) for x in sd)
        if abs(p_sum - 1.0) > tol:
            errs.append(f"score_dist p sum={p_sum:.4f} not within {tol} of 1 (add an 'other' bucket if needed)")
        distinct_scores = {str(x.get("score", "")) for x in sd if x.get("score")}
        if len(distinct_scores) < 10:
            errs.append(f"score_dist has {len(distinct_scores)} distinct scorelines, need at least 10")

    generated_wp = derive_win_probs_from_score_dist(sd)
    if sd and wp and generated_wp:
        outcome_tol = max(0.03, tol * 3)
        for outcome in ("home", "draw", "away"):
            if abs(float(wp.get(outcome, 0)) - float(generated_wp.get(outcome, 0))) > outcome_tol:
                errs.append(
                    f"generated score_dist aggregates to {outcome}={float(generated_wp.get(outcome, 0)):.3f} "
                    f"but win_probs.{outcome}={float(wp.get(outcome, 0)):.3f} "
                    f"(allowed ±{outcome_tol:.2f})"
                )

    reasoning = pred.get("reasoning") or {}
    for field, min_len in REQUIRED_REASONING_FIELDS.items():
        text = reasoning.get(field) or ""
        if len(str(text).strip()) < min_len:
            errs.append(f"reasoning.{field} too short ({len(str(text).strip())} chars, need ≥{min_len})")

    lineups = pred.get("lineups") or {}
    for side in ("home", "away"):
        _side = lineups.get(side)
        if isinstance(_side, list):
            starting = _side
        elif isinstance(_side, dict):
            starting = _side.get("starting") or []
        else:
            starting = []
        if len(starting) != 11:
            errs.append(f"lineups.{side}.starting has {len(starting)} players, need 11")

    # Consistency: explicit total-goals fields should reflect the score grid.
    if sd:
        p_sum = sum(float(x.get("p", 0)) for x in sd) or 1.0
        expected_from_scores = 0.0
        over_from_scores = {"over_1_5": 0.0, "over_2_5": 0.0, "over_3_5": 0.0, "over_4_5": 0.0}
        for item in sd:
            total_goals = score_total(str(item.get("score", "")))
            if total_goals is None:
                continue
            p = float(item.get("p", 0)) / p_sum
            expected_from_scores += total_goals * p
            if total_goals >= 2:
                over_from_scores["over_1_5"] += p
            if total_goals >= 3:
                over_from_scores["over_2_5"] += p
            if total_goals >= 4:
                over_from_scores["over_3_5"] += p
            if total_goals >= 5:
                over_from_scores["over_4_5"] += p

        expected_total = pred.get("expected_total_goals")
        if isinstance(expected_total, int | float):
            if abs(float(expected_total) - expected_from_scores) > 0.75:
                errs.append(
                    f"consistency: expected_total_goals={float(expected_total):.3f} "
                    f"but score_dist implies {expected_from_scores:.3f} (allowed ±0.75)"
                )
            profile = pred.get("match_profile")
            if profile == "low_event" and float(expected_total) > 2.6:
                errs.append("consistency: match_profile=low_event but expected_total_goals is above 2.6")
            if profile == "chaos" and float(expected_total) < 3.2:
                errs.append("consistency: match_profile=chaos but expected_total_goals is below 3.2")

        ou = pred.get("over_under_probs") or {}
        over_values = [float(ou.get(k, -1)) for k in ("over_1_5", "over_2_5", "over_3_5", "over_4_5")]
        if all(v >= 0 for v in over_values):
            if any(over_values[i] + 1e-9 < over_values[i + 1] for i in range(len(over_values) - 1)):
                errs.append("over_under_probs must be monotonic: over_1_5 >= over_2_5 >= over_3_5 >= over_4_5")
            for key, implied in over_from_scores.items():
                if abs(float(ou.get(key, 0)) - implied) > 0.25:
                    errs.append(
                        f"consistency: over_under_probs.{key}={float(ou.get(key, 0)):.3f} "
                        f"but score_dist implies {implied:.3f} (allowed ±0.25)"
                    )

    # Consistency: most_likely_score must be the highest-probability scoreline.
    most_likely = pred.get("most_likely_score")
    if sd and most_likely:
        max_p = max(float(x.get("p", 0)) for x in sd)
        top_scores = {str(x.get("score")) for x in sd if abs(float(x.get("p", 0)) - max_p) < 1e-9}
        if most_likely not in top_scores:
            errs.append(
                f"consistency: most_likely_score '{most_likely}' is not a highest-probability "
                f"score_dist entry {sorted(top_scores)}"
            )
        if favorite and score_outcome(str(most_likely)) != favorite:
            errs.append(
                f"consistency: most_likely_score outcome '{score_outcome(str(most_likely))}' "
                f"does not match highest win_probs bucket '{favorite}'"
            )

    stats = pred.get("stats") or {}
    required_keys = {"possession","shots","shots_on_target","corners","pass_accuracy","fouls","saves","defensive_actions"}
    missing = required_keys - set(stats.keys())
    if missing:
        errs.append(f"stats missing keys: {sorted(missing)}")
    for k in required_keys & set(stats.keys()):
        v = stats[k]
        if not (isinstance(v, dict) and "home" in v and "away" in v):
            errs.append(f"stats.{k} must be an object with home+away")

    return errs


def normalize_probabilities(pred: dict[str, Any], tol: float = 0.01) -> dict[str, Any]:
    """Normalize model-owned fields and generate score-derived fields.

    Models own `win_probs`, `headline_score`, `expected_total_goals`, and
    `expected_goal_diff`. The pipeline owns `score_dist`, `most_likely_score`,
    and `over_under_probs`.
    """
    out = strip_generated_score_fields(pred)
    wp = normalize_win_probs(out.get("win_probs"))
    if wp:
        out["win_probs"] = wp

    for scorer in out.get("scorers") or []:
        if "p" in scorer:
            scorer["p"] = round(float(scorer["p"]), 3)
    for assister in out.get("assisters") or []:
        if "p" in assister:
            assister["p"] = round(float(assister["p"]), 3)
    for motm in out.get("motm_probs") or []:
        if "p" in motm:
            motm["p"] = round(float(motm["p"]), 3)
    if isinstance(out.get("expected_total_goals"), int | float):
        out["expected_total_goals"] = round(float(out["expected_total_goals"]), 3)
    if isinstance(out.get("expected_goal_diff"), int | float):
        out["expected_goal_diff"] = round(float(out["expected_goal_diff"]), 3)

    generated, _ = calibrate_score_prediction(out)
    return generated


def _normalize_lineups(pred):
    """Tolerate models that emit lineups[side] as a flat starting list instead of
    {starting, bench}; normalize to object form so schema/semantic checks pass."""
    lu = pred.get("lineups") if isinstance(pred, dict) else None
    if isinstance(lu, dict):
        for side in ("home", "away"):
            v = lu.get(side)
            if isinstance(v, list):
                lu[side] = {"starting": v, "bench": []}


def validate(
    pred: dict[str, Any],
    *,
    fixture_id: str,
    setting_id: str,
    tol: float = 0.01,
) -> ValidationReport:
    pred, _ = calibrate_score_prediction(pred)
    _normalize_lineups(pred)
    rep = ValidationReport()
    for e in _validate_schema(pred):
        rep.add(f"schema: {e}")
    for e in _validate_semantics(pred, fixture_id=fixture_id, setting_id=setting_id, tol=tol):
        rep.add(f"semantic: {e}")
    return rep


def build_repair_prompt(original: dict[str, Any], report: ValidationReport) -> str:
    """Format a follow-up user message asking the model to fix only the listed issues."""
    return (
        "Your previous JSON failed format validation. Fix ONLY the listed issues "
        "and return the corrected FULL JSON object (not a patch). Keep all other "
        "fields and values unchanged. Do not add `score_dist`, `most_likely_score`, "
        "or `over_under_probs`; the system generates them from `win_probs`, "
        "`expected_total_goals`, and `headline_score`. Ensure `predicted_result`, "
        "`headline_score`, and the highest `win_probs` bucket all agree.\n\n"
        f"Validation errors:\n{report}\n\n"
        "Previous JSON:\n```json\n"
        f"{json.dumps(strip_generated_score_fields(original), ensure_ascii=False, indent=2)}\n```\n"
        "Return the corrected JSON only. Begin with `{`."
    )


def validate_or_repair(
    initial_pred: dict[str, Any],
    *,
    fixture_id: str,
    setting_id: str,
    retry_fn: Callable[[str], dict[str, Any]],
    max_retries: int = 2,
    tol: float = 0.01,
) -> tuple[dict[str, Any], ValidationReport, int]:
    """Validate; if invalid, try to repair up to max_retries times by
    re-querying via retry_fn(repair_prompt) -> new prediction dict.

    Returns (final_prediction, final_report, n_retries_used).
    """
    pred = normalize_probabilities(initial_pred, tol)
    rep = validate(pred, fixture_id=fixture_id, setting_id=setting_id, tol=tol)
    retries = 0
    while not rep.ok() and retries < max_retries:
        fix_prompt = build_repair_prompt(pred, rep)
        try:
            pred = retry_fn(fix_prompt)
        except Exception as e:  # noqa: BLE001
            rep.add(f"repair-call-error: {type(e).__name__}: {e}")
            break
        pred = normalize_probabilities(pred, tol)
        rep = validate(pred, fixture_id=fixture_id, setting_id=setting_id, tol=tol)
        retries += 1
    return pred, rep, retries
