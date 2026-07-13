"""Provisional grading for full-tournament predictions.

Until the 2026 World Cup finishes, the deepest fully observed target is the
semifinal field. This module therefore treats the confirmed final four as the
terminal result and can be rerun unchanged after the truth file is extended.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metrics import f1_set

ROOT = Path(__file__).resolve().parents[2]
TRUTH_PATH = ROOT / "configs" / "world_cup_2026_truth.json"
PREDICTIONS_DIR = ROOT / "data" / "tournament_predictions" / "world_cup_2026"


def _team_id(team: Any) -> str:
    if isinstance(team, dict):
        team = team.get("id") or team.get("name")
    return str(team or "").strip().casefold().replace(" ", "-")


def predicted_semifinalists(prediction: dict[str, Any]) -> list[str]:
    teams: list[str] = []
    for match in prediction.get("knockout_matches") or []:
        if str(match.get("stage") or "").upper() not in {"SF", "SEMIFINAL", "SEMI-FINAL"}:
            continue
        for side in ("home", "away"):
            team = _team_id(match.get(side))
            if team and team not in teams:
                teams.append(team)
    return teams


def predicted_semifinal_pairings(prediction: dict[str, Any]) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    for match in prediction.get("knockout_matches") or []:
        if str(match.get("stage") or "").upper() not in {"SF", "SEMIFINAL", "SEMI-FINAL"}:
            continue
        pair = frozenset({_team_id(match.get("home")), _team_id(match.get("away"))})
        if len(pair) == 2 and "" not in pair:
            pairs.add(pair)
    return pairs


def grade_tournament_prediction(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    predicted = predicted_semifinalists(prediction)
    actual = [_team_id(team) for team in truth.get("semifinalists") or []]
    correct = len(set(predicted) & set(actual))

    pred_pairs = predicted_semifinal_pairings(prediction)
    actual_pairs = {
        frozenset(_team_id(team) for team in pair)
        for pair in truth.get("semifinal_pairings") or []
    }
    pairing_correct = len(pred_pairs & actual_pairs)
    return {
        "as_of": truth.get("as_of"),
        "terminal_stage": truth.get("provisional_terminal_stage") or "SF",
        "predicted_semifinalists": predicted,
        "actual_semifinalists": actual,
        "semifinalist_correct": correct,
        "semifinalist_total": len(actual),
        "semifinalist_accuracy": correct / len(actual) if actual else None,
        "semifinalist_f1": f1_set(predicted, actual),
        "pairing_correct": pairing_correct,
        "pairing_total": len(actual_pairs),
        "pairing_accuracy": pairing_correct / len(actual_pairs) if actual_pairs else None,
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
