from __future__ import annotations

import unittest

from src.graders.grade_match import SCORING_VERSION, grade_match
from src.graders.grade_tournament import grade_tournament_prediction
from src.graders.metrics import (
    LAYER_CONTRAST_TEMPERATURE,
    contrast_calibrated_mean,
    contrast_calibrated_score,
    exact_score_accuracy,
    scoreline_calibrated_mean,
    scoreline_calibrated_score,
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
        self.assertGreater(high - low, 10.0)

    def test_leaderboard_contrast_is_applied_after_raw_macro_average(self) -> None:
        raw_mean, displayed = contrast_calibrated_mean([44.0, 52.0])
        self.assertEqual(raw_mean, 48.0)
        self.assertAlmostEqual(displayed, contrast_calibrated_score(48.0))
        self.assertNotAlmostEqual(
            displayed,
            (contrast_calibrated_score(44.0) + contrast_calibrated_score(52.0)) / 2,
        )

    def test_scoreline_contrast_spreads_current_range_after_aggregation(self) -> None:
        self.assertAlmostEqual(scoreline_calibrated_score(0), 0.0)
        self.assertAlmostEqual(scoreline_calibrated_score(100), 100.0)
        self.assertGreater(scoreline_calibrated_score(74), scoreline_calibrated_score(68))
        self.assertGreater(scoreline_calibrated_score(74) - scoreline_calibrated_score(68), 25.0)

        raw_mean, displayed = scoreline_calibrated_mean([68.0, 74.0])
        self.assertEqual(raw_mean, 71.0)
        self.assertAlmostEqual(displayed, scoreline_calibrated_score(71.0))

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
        self.assertAlmostEqual(
            result["layers"]["T1_core_result"],
            contrast_calibrated_score(
                result["raw_layers"]["T1_core_result"],
                temperature=LAYER_CONTRAST_TEMPERATURE,
            ),
        )


class TournamentMetricTests(unittest.TestCase):
    def test_comprehensive_provisional_tournament_grading(self) -> None:
        prediction = {
            "group_standings": {
                "A": [
                    {"team_id": "france", "rank": 1},
                    {"team_id": "spain", "rank": 2},
                    {"team_id": "england", "rank": 3},
                    {"team_id": "argentina", "rank": 4},
                ]
            },
            "knockout_matches": [
                {"stage": "R32", "home": {"id": "france"}, "away": {"id": "england"}},
                {"stage": "R32", "home": {"id": "spain"}, "away": {"id": "argentina"}},
                {"stage": "SF", "home": {"id": "france"}, "away": {"id": "spain"}},
                {"stage": "SF", "home": {"id": "brazil"}, "away": {"id": "argentina"}},
            ]
        }
        truth = {
            "as_of": "2026-07-13",
            "group_standings": {
                "A": ["france", "spain", "england", "argentina"],
            },
            "knockout_stages": {
                "R32": [
                    {"home": "france", "away": "spain"},
                    {"home": "england", "away": "argentina"},
                ],
                "SF": [
                    {"home": "france", "away": "spain"},
                    {"home": "england", "away": "argentina"},
                ],
            },
            "semifinalists": ["france", "spain", "england", "argentina"],
            "semifinal_pairings": [["france", "spain"], ["england", "argentina"]],
        }
        result = grade_tournament_prediction(prediction, truth)
        self.assertEqual(result["group_standings_score"], 100.0)
        self.assertEqual(result["stage_scores"]["R32"]["team_f1"], 100.0)
        self.assertEqual(result["stage_scores"]["R32"]["pairing_accuracy"], 0.0)
        self.assertEqual(result["stage_scores"]["SF"]["team_f1"], 75.0)
        self.assertEqual(result["stage_scores"]["SF"]["pairing_accuracy"], 50.0)
        self.assertAlmostEqual(result["advancement_score"], (100.0 + 8 * 75.0) / 9)
        self.assertAlmostEqual(result["pairing_score"], (0.0 + 8 * 50.0) / 9)
        self.assertAlmostEqual(
            result["t5_score"],
            (
                0.25 * 100.0
                + 0.35 * (0.70 * result["advancement_score"] + 0.30 * result["pairing_score"])
            ) / 0.60,
        )
        self.assertEqual(result["semifinalist_correct"], 3)
        self.assertEqual(result["semifinalist_f1"], 75.0)
        self.assertEqual(result["pairing_correct"], 1)

    def test_unobserved_tournament_targets_are_not_scored_as_zero(self) -> None:
        prediction = {
            "champion": {"id": "france"},
            "group_standings": {
                "A": [
                    {"team_id": "france", "rank": 1},
                    {"team_id": "spain", "rank": 2},
                ]
            },
        }
        truth = {"group_standings": {"A": ["france", "spain"]}}
        result = grade_tournament_prediction(prediction, truth)
        self.assertEqual(result["t5_score"], 100.0)
        self.assertEqual(result["available_weight"], 0.25)
        self.assertNotIn("champion", result["available_components"])


if __name__ == "__main__":
    unittest.main()
