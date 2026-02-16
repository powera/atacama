"""Tests for shared stats metric calculators."""

import unittest
from unittest.mock import patch, MagicMock

from trakaido.blueprints.stats_metrics import (
    compute_words_known,
    compute_daily_activity_summary,
    compute_member_summary,
)


class StatsMetricsTests(unittest.TestCase):
    def test_compute_words_known_uses_marked_as_known(self):
        payload = {
            "stats": {
                "w1": {"markedAsKnown": True, "directPractice": {}},
                "w2": {"markedAsKnown": False, "directPractice": {}},
                "w3": {"directPractice": {"multipleChoice_targetToEnglish": {"correct": 4, "incorrect": 0}}},
            }
        }

        self.assertEqual(compute_words_known(payload), 2)

    def test_compute_daily_activity_summary_aggregates_both_categories(self):
        payload = {
            "stats": {
                "w1": {
                    "directPractice": {
                        "multipleChoice_targetToEnglish": {"correct": 2, "incorrect": 1},
                    },
                    "contextualExposure": {
                        "sentences": {"correct": 3, "incorrect": 0},
                    },
                }
            }
        }

        summary = compute_daily_activity_summary(payload)

        self.assertEqual(summary["directPractice"]["totalAnswered"], 3)
        self.assertEqual(summary["contextualExposure"]["totalAnswered"], 3)
        self.assertEqual(summary["combined"]["totalAnswered"], 6)

    @patch("trakaido.blueprints.stats_metrics.get_journey_stats")
    def test_compute_member_summary_normalizes_payload(self, mock_get_journey_stats):
        mock_stats = MagicMock()
        mock_stats.stats = {
            "stats": {
                "w1": {
                    "exposed": True,
                    "markedAsKnown": True,
                    "directPractice": {"multipleChoice_targetToEnglish": {"correct": 1, "incorrect": 0}},
                    "contextualExposure": {},
                },
                "w2": {
                    "exposed": False,
                    "directPractice": {},
                    "contextualExposure": {},
                },
            }
        }
        mock_get_journey_stats.return_value = mock_stats

        summary = compute_member_summary("42", "lithuanian")

        self.assertEqual(summary["userId"], "42")
        self.assertEqual(summary["wordsTracked"], 2)
        self.assertEqual(summary["wordsExposed"], 1)
        self.assertEqual(summary["wordsKnown"], 1)
        self.assertIn("activitySummary", summary)


if __name__ == "__main__":
    unittest.main()
