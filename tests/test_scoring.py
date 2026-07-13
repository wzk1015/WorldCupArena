from __future__ import annotations

import unittest

from src.graders.grade_match import SCORING_VERSION, grade_match
from src.graders.grade_tournament import grade_tournament_prediction
from src.graders.metrics import (
    contrast_calibrated_score,
    exact_score_accuracy,
    scoreline_similarity,
)


class ScoreMetricTests(unittest.TestCase):
    def test_exact_and_partial_scoreline_metrics(self) -> None:
        self.assertEqual(exact_score_accuracy("2-1", "2-1"), 100.0)
        self.assertEqual(exact_score_accuracy("1-0", "2-1"), 0.0)
        self.assertEqual(scoreline_similarity("2-1", "2-1"), 100.0)
        self.assertGreater(scoreline_similarity("1-0", "2-1"), scoreline_similarity("0-1", "2-1"))

    def test_contrast_transform_is_fixed_monotonic_and_spreads_midrange(self) -> None:
        self.assertAlmostEqual(contrast_calibrated_score(0), 0.0)
        self.assertAlmostEqual(contrast_calibrated_score(100), 100.0)
        low = contrast_calibrated_score(44)
        high = contrast_calibrated_score(47)
        self.assertGreater(high, low)
        self.assertGreater(high - low, 3.0)

    def test_grade_match_excludes_tasks_without_truth(self) -> None:
        prediction = {
            "win_probs": {"home": 0.7, "draw": 0.2, "away": 0.1},
            "headline_score": "2-1",
            "expected_goal_diff": 1.0,
        }
        truth = {"result": "home", "score": "2-1", "goal_diff": 1}
        result = grade_match(prediction, truth)
        self.assertEqual(result["scoring_version"], SCORING_VERSION)
        self.assertEqual(set(result["raw_layers"]), {"T1_core_result"})
        self.assertFalse(result["tasks"]["man_of_the_match"]["available"])
        self.assertTrue(result["tasks"]["exact_score"]["available"])
        self.assertGreater(result["composite"], result["raw_composite"])


class TournamentMetricTests(unittest.TestCase):
    def test_provisional_semifinal_grading(self) -> None:
        prediction = {
            "knockout_matches": [
                {"stage": "SF", "home": {"id": "france"}, "away": {"id": "spain"}},
                {"stage": "SF", "home": {"id": "brazil"}, "away": {"id": "argentina"}},
            ]
        }
        truth = {
            "as_of": "2026-07-13",
            "semifinalists": ["france", "spain", "england", "argentina"],
            "semifinal_pairings": [["france", "spain"], ["england", "argentina"]],
        }
        result = grade_tournament_prediction(prediction, truth)
        self.assertEqual(result["semifinalist_correct"], 3)
        self.assertEqual(result["semifinalist_f1"], 75.0)
        self.assertEqual(result["pairing_correct"], 1)


if __name__ == "__main__":
    unittest.main()
