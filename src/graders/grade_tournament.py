"""Availability-aware grading for full-tournament predictions.

The score expands as tournament truth becomes observable.  Group standings are
graded for rank agreement, while every known knockout round is graded for both
the teams that reached it and the exact pairings.  Unobserved outcomes such as
individual awards are excluded instead of being scored zero.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .metrics import f1_set, kendall_tau

ROOT = Path(__file__).resolve().parents[2]
TRUTH_PATH = ROOT / "configs" / "world_cup_2026_truth.json"
PREDICTIONS_DIR = ROOT / "data" / "tournament_predictions" / "world_cup_2026"

GROUP_COMPONENT_WEIGHT = 0.25
BRACKET_COMPONENT_WEIGHT = 0.35
CHAMPION_COMPONENT_WEIGHT = 0.20
ADVANCEMENT_SHARE = 0.70
PAIRING_SHARE = 0.30
STAGE_WEIGHTS = {"R32": 1.0, "R16": 2.0, "QF": 4.0, "SF": 8.0, "FINAL": 16.0}

TEAM_ALIASES = {
    "cape-verde-islands": "cape-verde",
    "congo-dr": "dr-congo",
    "cote-d-ivoire": "ivory-coast",
    "curacao": "cura-ao",
    "korea-republic": "south-korea",
    "turkiye": "turkey",
}

STAGE_ALIASES = {
    "ROUND-OF-32": "R32",
    "ROUND-OF-16": "R16",
    "QUARTER-FINAL": "QF",
    "QUARTER-FINALS": "QF",
    "QUARTERFINAL": "QF",
    "QUARTERFINALS": "QF",
    "SEMIFINAL": "SF",
    "SEMI-FINAL": "SF",
    "SEMIFINALS": "SF",
    "SEMI-FINALS": "SF",
}


def _team_id(team: Any) -> str:
    if isinstance(team, dict):
        team = team.get("id") or team.get("team_id") or team.get("name") or team.get("team")
    value = unicodedata.normalize("NFD", str(team or ""))
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return TEAM_ALIASES.get(value, value)


def _stage_id(stage: Any) -> str:
    value = str(stage or "").strip().upper().replace("_", " ").replace(" ", "-")
    return STAGE_ALIASES.get(value, value)


def _ordered_group(group_rows: Any) -> list[str]:
    if not isinstance(group_rows, list):
        return []
    indexed = list(enumerate(group_rows))
    indexed.sort(key=lambda item: (
        item[1].get("rank", item[0] + 1) if isinstance(item[1], dict) else item[0] + 1,
        item[0],
    ))
    return [_team_id(row) for _, row in indexed if _team_id(row)]


def _group_scores(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, float]:
    pred_groups = prediction.get("group_standings") or {}
    truth_groups = truth.get("group_standings") or {}
    scores: dict[str, float] = {}
    for group, truth_rows in sorted(truth_groups.items()):
        actual = [_team_id(team) for team in truth_rows if _team_id(team)]
        predicted = _ordered_group(pred_groups.get(group) or pred_groups.get(str(group).upper()) or [])
        if not actual:
            continue
        coverage = f1_set(predicted, actual) / 100.0
        scores[str(group).upper()] = kendall_tau(predicted, actual) * coverage
    return scores


def _matches_for_stage(source: dict[str, Any], stage: str, *, truth: bool = False) -> list[dict[str, Any]]:
    if truth:
        rows = (source.get("knockout_stages") or {}).get(stage) or []
    else:
        rows = [
            match for match in source.get("knockout_matches") or []
            if _stage_id(match.get("stage")) == stage
        ]
    return [row for row in rows if isinstance(row, dict)]


def _participants(matches: list[dict[str, Any]]) -> list[str]:
    teams: list[str] = []
    for match in matches:
        for side in ("home", "away"):
            team = _team_id(match.get(side))
            if team and team not in teams:
                teams.append(team)
    return teams


def _pairings(matches: list[dict[str, Any]]) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    for match in matches:
        pair = frozenset({_team_id(match.get("home")), _team_id(match.get("away"))})
        if len(pair) == 2 and "" not in pair:
            pairs.add(pair)
    return pairs


def predicted_semifinalists(prediction: dict[str, Any]) -> list[str]:
    return _participants(_matches_for_stage(prediction, "SF"))


def predicted_semifinal_pairings(prediction: dict[str, Any]) -> set[frozenset[str]]:
    return _pairings(_matches_for_stage(prediction, "SF"))


def _weighted_mean(values: dict[str, float]) -> float | None:
    available = [(value, STAGE_WEIGHTS[stage]) for stage, value in values.items() if stage in STAGE_WEIGHTS]
    denominator = sum(weight for _, weight in available)
    if not denominator:
        return None
    return sum(value * weight for value, weight in available) / denominator


def grade_tournament_prediction(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    group_scores = _group_scores(prediction, truth)
    group_score = sum(group_scores.values()) / len(group_scores) if group_scores else None

    stage_scores: dict[str, dict[str, Any]] = {}
    advancement_by_stage: dict[str, float] = {}
    pairing_by_stage: dict[str, float] = {}
    for stage in STAGE_WEIGHTS:
        actual_matches = _matches_for_stage(truth, stage, truth=True)
        if not actual_matches:
            continue
        predicted_matches = _matches_for_stage(prediction, stage)
        actual_teams = _participants(actual_matches)
        predicted_teams = _participants(predicted_matches)
        actual_pairs = _pairings(actual_matches)
        predicted_pairs = _pairings(predicted_matches)
        team_f1 = f1_set(predicted_teams, actual_teams)
        pairing_accuracy = 100.0 * len(predicted_pairs & actual_pairs) / len(actual_pairs) if actual_pairs else 0.0
        advancement_by_stage[stage] = team_f1
        pairing_by_stage[stage] = pairing_accuracy
        stage_scores[stage] = {
            "weight": STAGE_WEIGHTS[stage],
            "team_f1": team_f1,
            "pairing_accuracy": pairing_accuracy,
            "predicted_team_count": len(set(predicted_teams)),
            "actual_team_count": len(set(actual_teams)),
            "pairing_correct": len(predicted_pairs & actual_pairs),
            "pairing_total": len(actual_pairs),
        }

    advancement_score = _weighted_mean(advancement_by_stage)
    pairing_score = _weighted_mean(pairing_by_stage)
    bracket_score = None
    if advancement_score is not None and pairing_score is not None:
        bracket_score = ADVANCEMENT_SHARE * advancement_score + PAIRING_SHARE * pairing_score

    available_components: dict[str, dict[str, float]] = {}
    if group_score is not None:
        available_components["group_standings"] = {
            "score": group_score,
            "configured_weight": GROUP_COMPONENT_WEIGHT,
        }
    if bracket_score is not None:
        available_components["knockout_bracket"] = {
            "score": bracket_score,
            "configured_weight": BRACKET_COMPONENT_WEIGHT,
        }
    actual_champion = _team_id(truth.get("champion"))
    predicted_champion = _team_id(prediction.get("champion"))
    champion_score = None
    if actual_champion:
        champion_score = 100.0 if predicted_champion == actual_champion else 0.0
        available_components["champion"] = {
            "score": champion_score,
            "configured_weight": CHAMPION_COMPONENT_WEIGHT,
        }
    available_weight = sum(item["configured_weight"] for item in available_components.values())
    t5_score = (
        sum(item["score"] * item["configured_weight"] for item in available_components.values())
        / available_weight
        if available_weight else None
    )

    predicted_sf = predicted_semifinalists(prediction)
    actual_sf = _participants(_matches_for_stage(truth, "SF", truth=True))
    if not actual_sf:
        actual_sf = [_team_id(team) for team in truth.get("semifinalists") or []]
    pred_sf_pairs = predicted_semifinal_pairings(prediction)
    actual_sf_pairs = _pairings(_matches_for_stage(truth, "SF", truth=True))
    if not actual_sf_pairs:
        actual_sf_pairs = {
            frozenset(_team_id(team) for team in pair)
            for pair in truth.get("semifinal_pairings") or []
        }
    semifinal_correct = len(set(predicted_sf) & set(actual_sf))
    pairing_correct = len(pred_sf_pairs & actual_sf_pairs)

    return {
        "as_of": truth.get("as_of"),
        "terminal_stage": truth.get("provisional_terminal_stage") or (list(stage_scores)[-1] if stage_scores else None),
        "group_standings_score": group_score,
        "group_scores": group_scores,
        "advancement_score": advancement_score,
        "pairing_score": pairing_score,
        "bracket_score": bracket_score,
        "champion_score": champion_score,
        "predicted_champion": predicted_champion or None,
        "actual_champion": actual_champion or None,
        "stage_scores": stage_scores,
        "bracket_mix": {"advancement": ADVANCEMENT_SHARE, "pairings": PAIRING_SHARE},
        "available_components": available_components,
        "available_weight": available_weight,
        "t5_score": t5_score,
        "predicted_semifinalists": predicted_sf,
        "actual_semifinalists": actual_sf,
        "semifinalist_correct": semifinal_correct,
        "semifinalist_total": len(actual_sf),
        "semifinalist_accuracy": semifinal_correct / len(actual_sf) if actual_sf else None,
        "semifinalist_f1": f1_set(predicted_sf, actual_sf),
        "pairing_correct": pairing_correct,
        "pairing_total": len(actual_sf_pairs),
        "pairing_accuracy": pairing_correct / len(actual_sf_pairs) if actual_sf_pairs else None,
    }


def main() -> None:
    truth = json.loads(TRUTH_PATH.read_text())
    rows = []
    for path in sorted(PREDICTIONS_DIR.glob("*.json")):
        record = json.loads(path.read_text())
        rows.append({
            "model_id": record.get("model_id") or path.stem,
            "setting": record.get("setting"),
            **grade_tournament_prediction(record.get("prediction") or {}, truth),
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
