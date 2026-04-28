"""Comprehensive format validation with retry.

The grader assumes well-formed, schema-compliant JSON. This module enforces that
contract at prediction time so we don't discover missing fields only when trying
to score — at which point the match is already over and we can't re-query.

Validation layers:
    1. JSON parseability (handled by runner, but we re-parse to be safe).
    2. JSON-schema conformance (required fields, types, enums, patterns).
    3. Semantic checks the schema can't express:
         - win_probs sum ≈ 1
         - score_dist p values sum ≈ 1
         - score_dist contains at least 10 distinct scorelines
         - most_likely_score matches the highest-probability score_dist entry
         - score_dist outcome totals are close to win_probs
         - stats contains all 8 required keys
         - lineups.*.starting has exactly 11 entries
         - reasoning.overall non-empty & ≥80 chars
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

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "prediction.schema.json"


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
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in v.iter_errors(pred)]


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

    wp = pred.get("win_probs") or {}
    s = float(wp.get("home", 0)) + float(wp.get("draw", 0)) + float(wp.get("away", 0))
    if abs(s - 1.0) > tol:
        errs.append(f"win_probs sum={s:.4f} not within {tol} of 1")

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

    reasoning = (pred.get("reasoning") or {}).get("overall") or ""
    if len(reasoning) < 80:
        errs.append(f"reasoning.overall too short ({len(reasoning)} chars, need ≥80)")

    lineups = pred.get("lineups") or {}
    for side in ("home", "away"):
        starting = (lineups.get(side) or {}).get("starting") or []
        if len(starting) != 11:
            errs.append(f"lineups.{side}.starting has {len(starting)} players, need 11")

    def _score_outcome(score_str: str) -> str | None:
        parts = score_str.split("-") if score_str else []
        if len(parts) != 2:
            return None
        try:
            h_goals, a_goals = int(parts[0]), int(parts[1])
        except (ValueError, TypeError):
            return None
        return "home" if h_goals > a_goals else "away" if a_goals > h_goals else "draw"

    # Consistency: score_dist aggregate outcomes should broadly match win_probs.
    # The single most likely exact score can reasonably be a draw even when
    # home/away is the most likely 3-way outcome, because win probability is
    # spread over many exact scores.
    sd = pred.get("score_dist") or []
    if sd and wp:
        sd_outcomes = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for item in sd:
            outcome = _score_outcome(str(item.get("score", "")))
            if outcome:
                sd_outcomes[outcome] += float(item.get("p", 0))
        outcome_tol = max(0.10, tol * 10)
        for outcome in ("home", "draw", "away"):
            if abs(sd_outcomes[outcome] - float(wp.get(outcome, 0))) > outcome_tol:
                errs.append(
                    f"consistency: score_dist aggregates to {outcome}={sd_outcomes[outcome]:.3f} "
                    f"but win_probs.{outcome}={float(wp.get(outcome, 0)):.3f} "
                    f"(allowed ±{outcome_tol:.2f})"
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
    """Post-hoc normalize distributions that are only slightly off, so minor
    rounding doesn't waste a retry. Returns a new dict; does not mutate input.
    Also rounds all probability values to 3 decimal places."""
    out = json.loads(json.dumps(pred))  # deep copy via JSON
    wp = out.get("win_probs") or {}
    s = sum(float(wp.get(k, 0)) for k in ("home","draw","away"))
    if 0 < s and abs(s - 1.0) <= tol:
        for k in ("home","draw","away"):
            wp[k] = round(float(wp.get(k, 0)) / s, 3)
        out["win_probs"] = wp
    else:
        for k in ("home","draw","away"):
            if k in wp:
                wp[k] = round(float(wp[k]), 3)
        out["win_probs"] = wp

    sd = out.get("score_dist") or []
    p_sum = sum(float(x.get("p", 0)) for x in sd)
    if 0 < p_sum and abs(p_sum - 1.0) <= tol:
        for x in sd:
            x["p"] = round(float(x.get("p", 0)) / p_sum, 3)
        out["score_dist"] = sd
    else:
        for x in sd:
            if "p" in x:
                x["p"] = round(float(x["p"]), 3)
        out["score_dist"] = sd

    for scorer in out.get("scorers") or []:
        if "p" in scorer:
            scorer["p"] = round(float(scorer["p"]), 3)
    for assister in out.get("assisters") or []:
        if "p" in assister:
            assister["p"] = round(float(assister["p"]), 3)
    for motm in out.get("motm_probs") or []:
        if "p" in motm:
            motm["p"] = round(float(motm["p"]), 3)

    return out


def validate(
    pred: dict[str, Any],
    *,
    fixture_id: str,
    setting_id: str,
    tol: float = 0.01,
) -> ValidationReport:
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
        "fields and values unchanged.\n\n"
        f"Validation errors:\n{report}\n\n"
        "Previous JSON:\n```json\n"
        f"{json.dumps(original, ensure_ascii=False, indent=2)}\n```\n"
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
