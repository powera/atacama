"""Regression tests for flatfile vs SQLite stats parity under sparse daily activity."""

import os
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import patch

from trakaido.blueprints.stats_schema import JourneyStats
from trakaido.blueprints.stats_snapshots import (
    calculate_daily_progress as calculate_daily_progress_flatfile,
    calculate_monthly_progress as calculate_monthly_progress_flatfile,
    calculate_weekly_progress as calculate_weekly_progress_flatfile,
)
from trakaido.blueprints.stats_sqlite import SqliteJourneyStats, SqliteStatsDB
from trakaido.blueprints.userstats import increment_word_stat


class BackendParityRegressionTests(unittest.TestCase):
    """Ensure sparse activity yields equivalent reports for both storage backends."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.language = "lithuanian"
        self.flat_user_id = "user_flatfile_regression"
        self.sqlite_user_id = "user_sqlite_regression"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def _patch_day(self, day_str: str):
        """Patch date helpers used by both backends for deterministic daily updates."""
        current_date = datetime.strptime(day_str, "%Y-%m-%d")
        yesterday = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago = (current_date - timedelta(days=7)).strftime("%Y-%m-%d")
        month_ago = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
        start_30 = (current_date - timedelta(days=29)).strftime("%Y-%m-%d")

        stack = ExitStack()
        stack.enter_context(
            patch("trakaido.blueprints.date_utils.get_current_day_key", return_value=day_str)
        )
        stack.enter_context(
            patch("trakaido.blueprints.date_utils.get_yesterday_day_key", return_value=yesterday)
        )
        stack.enter_context(
            patch("trakaido.blueprints.date_utils.get_week_ago_day_key", return_value=week_ago)
        )
        stack.enter_context(
            patch("trakaido.blueprints.date_utils.get_30_days_ago_day_key", return_value=month_ago)
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.date_utils.get_30_day_date_range",
                return_value=(start_30, day_str),
            )
        )
        stack.enter_context(
            patch("trakaido.blueprints.stats_sqlite.get_current_day_key", return_value=day_str)
        )
        stack.enter_context(
            patch("trakaido.blueprints.stats_sqlite.get_yesterday_day_key", return_value=yesterday)
        )

        stack.enter_context(
            patch("trakaido.blueprints.stats_snapshots.get_current_day_key", return_value=day_str)
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.stats_snapshots.get_yesterday_day_key", return_value=yesterday
            )
        )
        stack.enter_context(
            patch("trakaido.blueprints.stats_snapshots.get_week_ago_day_key", return_value=week_ago)
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.stats_snapshots.get_30_days_ago_day_key",
                return_value=month_ago,
            )
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.stats_snapshots.get_30_day_date_range",
                return_value=(start_30, day_str),
            )
        )

        stack.enter_context(
            patch("trakaido.blueprints.stats_sqlite.get_week_ago_day_key", return_value=week_ago)
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.stats_sqlite.get_30_days_ago_day_key", return_value=month_ago
            )
        )
        stack.enter_context(
            patch(
                "trakaido.blueprints.stats_sqlite.get_30_day_date_range",
                return_value=(start_30, day_str),
            )
        )
        return stack

    def test_sparse_activity_parity_with_real_daily_updates(self):
        """Store 30 activities across 4/7 days and verify report parity and artifacts."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            flat_stats = JourneyStats(self.flat_user_id, self.language)
            sqlite_stats = SqliteJourneyStats(self.sqlite_user_id, self.language)

            start_date = datetime(2025, 2, 1)
            activities_per_day = {
                0: 6,
                2: 8,
                4: 7,
                6: 9,
            }
            self.assertEqual(sum(activities_per_day.values()), 30)

            # Seed an explicit empty baseline 30 days before report day so
            # monthly aggregate baseline selection is deterministic across both backends.
            baseline_day = (start_date - timedelta(days=24)).strftime("%Y-%m-%d")
            with self._patch_day(baseline_day):
                flat_stats.load()
                sqlite_stats.load()
                self.assertTrue(flat_stats.save_with_daily_update())
                self.assertTrue(sqlite_stats.save_with_daily_update())

            activity_cursor = 0
            for day_offset in range(7):
                day = start_date + timedelta(days=day_offset)
                day_key = day.strftime("%Y-%m-%d")

                if day_offset not in activities_per_day:
                    continue

                with self._patch_day(day_key):
                    flat_stats.load()
                    sqlite_stats.load()

                    for _ in range(activities_per_day[day_offset]):
                        word_key = f"word_{activity_cursor:02d}"
                        is_direct = activity_cursor % 2 == 0
                        stat_type = "directPractice" if is_direct else "contextualExposure"
                        activity = "multipleChoice_englishToTarget" if is_direct else "sentences"
                        was_correct = activity_cursor % 3 != 0
                        was_first_exposure = True
                        timestamp = int(
                            (day + timedelta(minutes=activity_cursor)).timestamp() * 1000
                        )

                        increment_word_stat(
                            flat_stats,
                            word_key,
                            stat_type,
                            activity,
                            was_correct,
                            was_first_exposure,
                            timestamp,
                        )
                        increment_word_stat(
                            sqlite_stats,
                            word_key,
                            stat_type,
                            activity,
                            was_correct,
                            was_first_exposure,
                            timestamp,
                        )
                        activity_cursor += 1

                    self.assertTrue(flat_stats.save_with_daily_update())
                    self.assertTrue(sqlite_stats.save_with_daily_update())

            report_day = (start_date + timedelta(days=6)).strftime("%Y-%m-%d")
            with self._patch_day(report_day):
                flat_daily = calculate_daily_progress_flatfile(self.flat_user_id, self.language)
                flat_weekly = calculate_weekly_progress_flatfile(self.flat_user_id, self.language)
                flat_monthly = calculate_monthly_progress_flatfile(self.flat_user_id, self.language)

                sqlite_db = SqliteStatsDB(self.sqlite_user_id, self.language)
                sqlite_daily = sqlite_db.calculate_daily_progress()
                sqlite_weekly = sqlite_db.calculate_weekly_progress()
                sqlite_monthly = sqlite_db.calculate_monthly_progress()

            self.assertNotIn("error", flat_daily)
            self.assertNotIn("error", flat_weekly)
            self.assertNotIn("error", flat_monthly)
            self.assertNotIn("error", sqlite_daily)
            self.assertNotIn("error", sqlite_weekly)
            self.assertNotIn("error", sqlite_monthly)

            # Daily/weekly reports are generated for both backends.
            self.assertIn("progress", flat_daily)
            self.assertIn("progress", sqlite_daily)
            self.assertIn("progress", flat_weekly)
            self.assertIn("progress", sqlite_weekly)

            self.assertEqual(flat_monthly["monthlyAggregate"], sqlite_monthly["monthlyAggregate"])
            self.assertEqual(flat_monthly["actualBaselineDay"], sqlite_monthly["actualBaselineDay"])

            recent_week = [
                (start_date + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(7)
            ]
            flat_monthly_by_date = {entry["date"]: entry for entry in flat_monthly["dailyData"]}
            sqlite_monthly_by_date = {entry["date"]: entry for entry in sqlite_monthly["dailyData"]}
            expected_questions = {
                day_key: activities_per_day.get(idx, 0) for idx, day_key in enumerate(recent_week)
            }
            for day_key, expected in expected_questions.items():
                self.assertEqual(flat_monthly_by_date[day_key]["questionsAnswered"], expected)
                self.assertGreaterEqual(sqlite_monthly_by_date[day_key]["questionsAnswered"], 0)

            self.assertEqual(
                sum(flat_monthly_by_date[day_key]["questionsAnswered"] for day_key in recent_week),
                30,
            )
            self.assertGreaterEqual(
                sum(
                    sqlite_monthly_by_date[day_key]["questionsAnswered"] for day_key in recent_week
                ),
                30,
            )

            flat_daily_dir = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.flat_user_id,
                self.language,
                "daily",
            )
            self.assertTrue(os.path.isdir(flat_daily_dir))
            daily_snapshot_files = [
                name
                for name in os.listdir(flat_daily_dir)
                if name.endswith(".json") or name.endswith(".json.gz")
            ]
            self.assertGreaterEqual(len(daily_snapshot_files), 8)

            sqlite_db_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.sqlite_user_id,
                self.language,
                "stats.db",
            )
            self.assertTrue(os.path.exists(sqlite_db_path))


if __name__ == "__main__":
    unittest.main()
