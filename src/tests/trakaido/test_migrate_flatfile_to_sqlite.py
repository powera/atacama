"""Tests for the flat-file to SQLite migration script."""

import gzip
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from trakaido.blueprints.stats_schema import (
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
    create_empty_word_stats,
)

# Import the migration module (lives under tools/, added to sys.path below)
import sys
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "tools")
)

from migrate_flatfile_to_sqlite import (
    compute_snapshot_aggregates,
    discover_snapshot_dates,
    discover_users,
    load_flat_file_stats,
    load_snapshot,
    migrate_user,
)


def _make_word(exposed=True, mc_correct=0, mc_incorrect=0, last_seen=None):
    """Helper to create a word stats dict with common settings."""
    ws = create_empty_word_stats()
    ws["exposed"] = exposed
    ws["directPractice"]["multipleChoice_englishToTarget"]["correct"] = mc_correct
    ws["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = mc_incorrect
    if last_seen is not None:
        ws["practiceHistory"]["lastSeen"] = last_seen
    return ws


class ComputeSnapshotAggregatesTests(unittest.TestCase):
    """Test the aggregate computation from per-word snapshot data."""

    def test_empty_stats(self):
        exposed, total_q, totals = compute_snapshot_aggregates({"stats": {}})
        self.assertEqual(exposed, 0)
        self.assertEqual(total_q, 0)

    def test_single_word(self):
        stats = {"stats": {"w1": _make_word(exposed=True, mc_correct=5, mc_incorrect=2)}}
        exposed, total_q, totals = compute_snapshot_aggregates(stats)
        self.assertEqual(exposed, 1)
        self.assertEqual(total_q, 7)
        self.assertEqual(
            totals["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5
        )
        self.assertEqual(
            totals["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 2
        )

    def test_multiple_words(self):
        stats = {
            "stats": {
                "w1": _make_word(exposed=True, mc_correct=3, mc_incorrect=1),
                "w2": _make_word(exposed=True, mc_correct=7, mc_incorrect=0),
                "w3": _make_word(exposed=False, mc_correct=0, mc_incorrect=0),
            }
        }
        exposed, total_q, totals = compute_snapshot_aggregates(stats)
        self.assertEqual(exposed, 2)
        self.assertEqual(total_q, 11)

    def test_contextual_exposure_counted(self):
        ws = create_empty_word_stats()
        ws["exposed"] = True
        ws["contextualExposure"]["sentences"]["correct"] = 10
        ws["contextualExposure"]["sentences"]["incorrect"] = 3
        stats = {"stats": {"w1": ws}}

        exposed, total_q, totals = compute_snapshot_aggregates(stats)
        self.assertEqual(total_q, 13)
        self.assertEqual(totals["contextualExposure"]["sentences"]["correct"], 10)


class DiscoverUsersTests(unittest.TestCase):
    """Test user discovery from the data directory."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_data_dir)

    def test_no_users(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            users = discover_users("lithuanian")
            self.assertEqual(users, [])

    def test_finds_users_with_stats(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            # Create two users with stats.json
            for uid in ["user_a", "user_b"]:
                user_dir = os.path.join(self.test_data_dir, "trakaido", uid, "lithuanian")
                os.makedirs(user_dir)
                with open(os.path.join(user_dir, "stats.json"), "w") as f:
                    json.dump({"stats": {}}, f)

            # Create a user without stats.json
            os.makedirs(os.path.join(self.test_data_dir, "trakaido", "user_c", "lithuanian"))

            users = discover_users("lithuanian")
            self.assertEqual(users, ["user_a", "user_b"])

    def test_language_specific(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            # User has lithuanian but not chinese
            user_dir = os.path.join(self.test_data_dir, "trakaido", "user_a", "lithuanian")
            os.makedirs(user_dir)
            with open(os.path.join(user_dir, "stats.json"), "w") as f:
                json.dump({"stats": {}}, f)

            self.assertEqual(discover_users("lithuanian"), ["user_a"])
            self.assertEqual(discover_users("chinese"), [])


class DiscoverSnapshotDatesTests(unittest.TestCase):
    """Test snapshot date discovery."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_data_dir)

    def test_no_snapshots(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            dates = discover_snapshot_dates("user1", "lithuanian")
            self.assertEqual(dates, [])

    def test_finds_json_and_gzip_snapshots(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            daily_dir = os.path.join(
                self.test_data_dir, "trakaido", "user1", "lithuanian", "daily"
            )
            os.makedirs(daily_dir)

            # Create a plain JSON snapshot
            with open(os.path.join(daily_dir, "2025-01-15_current.json"), "w") as f:
                json.dump({"stats": {}}, f)

            # Create a gzip snapshot
            with gzip.open(os.path.join(daily_dir, "2025-01-14_current.json.gz"), "wt") as f:
                json.dump({"stats": {}}, f)

            # Create a "yesterday" snapshot (should be ignored)
            with open(os.path.join(daily_dir, "2025-01-15_yesterday.json"), "w") as f:
                json.dump({"stats": {}}, f)

            dates = discover_snapshot_dates("user1", "lithuanian")
            self.assertEqual(dates, ["2025-01-14", "2025-01-15"])


class LoadSnapshotTests(unittest.TestCase):
    """Test loading snapshots from flat files."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_data_dir)

    def test_load_json_snapshot(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            daily_dir = os.path.join(
                self.test_data_dir, "trakaido", "user1", "lithuanian", "daily"
            )
            os.makedirs(daily_dir)

            data = {"stats": {"w1": _make_word(mc_correct=5)}}
            with open(os.path.join(daily_dir, "2025-01-15_current.json"), "w") as f:
                json.dump(data, f)

            loaded = load_snapshot("user1", "lithuanian", "2025-01-15")
            self.assertIsNotNone(loaded)
            self.assertIn("w1", loaded["stats"])

    def test_load_gzip_snapshot(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            daily_dir = os.path.join(
                self.test_data_dir, "trakaido", "user1", "lithuanian", "daily"
            )
            os.makedirs(daily_dir)

            data = {"stats": {"w1": _make_word(mc_correct=3)}}
            with gzip.open(
                os.path.join(daily_dir, "2025-01-14_current.json.gz"), "wt"
            ) as f:
                json.dump(data, f)

            loaded = load_snapshot("user1", "lithuanian", "2025-01-14")
            self.assertIsNotNone(loaded)
            self.assertIn("w1", loaded["stats"])

    def test_gzip_preferred_over_json(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            daily_dir = os.path.join(
                self.test_data_dir, "trakaido", "user1", "lithuanian", "daily"
            )
            os.makedirs(daily_dir)

            # Write different data to json and gzip
            json_data = {"stats": {"json_word": _make_word()}}
            gz_data = {"stats": {"gz_word": _make_word()}}

            with open(os.path.join(daily_dir, "2025-01-15_current.json"), "w") as f:
                json.dump(json_data, f)
            with gzip.open(
                os.path.join(daily_dir, "2025-01-15_current.json.gz"), "wt"
            ) as f:
                json.dump(gz_data, f)

            loaded = load_snapshot("user1", "lithuanian", "2025-01-15")
            self.assertIn("gz_word", loaded["stats"])

    def test_missing_snapshot_returns_none(self):
        with patch("constants.DATA_DIR", self.test_data_dir):
            loaded = load_snapshot("user1", "lithuanian", "2025-01-15")
            self.assertIsNone(loaded)


class MigrateUserTests(unittest.TestCase):
    """Test end-to-end migration of a single user."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_data_dir)

    def _create_user_data(self, user_id, language, stats_data, snapshots=None):
        """Helper to set up flat-file data for a user."""
        user_dir = os.path.join(self.test_data_dir, "trakaido", user_id, language)
        os.makedirs(user_dir, exist_ok=True)

        with open(os.path.join(user_dir, "stats.json"), "w") as f:
            json.dump(stats_data, f)

        if snapshots:
            daily_dir = os.path.join(user_dir, "daily")
            os.makedirs(daily_dir, exist_ok=True)
            for date, data in snapshots.items():
                with open(os.path.join(daily_dir, f"{date}_current.json"), "w") as f:
                    json.dump(data, f)

    def test_migrate_word_stats(self):
        """Test that word stats are correctly migrated."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {
                "stats": {
                    "w1": _make_word(
                        exposed=True, mc_correct=10, mc_incorrect=3, last_seen=1704067200000
                    ),
                    "w2": _make_word(exposed=True, mc_correct=5, mc_incorrect=1),
                    "w3": _make_word(exposed=False),
                }
            }
            self._create_user_data("test_user", "lithuanian", stats)

            result = migrate_user("test_user", "lithuanian")
            self.assertTrue(result)

            # Verify via SqliteStatsDB
            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")
            loaded = db.get_all_stats()

            self.assertEqual(len(loaded["stats"]), 3)
            self.assertTrue(loaded["stats"]["w1"]["exposed"])
            self.assertEqual(
                loaded["stats"]["w1"]["directPractice"]["multipleChoice_englishToTarget"]["correct"],
                10,
            )
            self.assertEqual(
                loaded["stats"]["w1"]["practiceHistory"]["lastSeen"],
                1704067200000,
            )
            self.assertFalse(loaded["stats"]["w3"]["exposed"])

    def test_migrate_snapshots(self):
        """Test that daily snapshots are correctly migrated."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word(exposed=True, mc_correct=10)}}
            day1_stats = {"stats": {"w1": _make_word(exposed=True, mc_correct=5)}}
            day2_stats = {"stats": {"w1": _make_word(exposed=True, mc_correct=10)}}

            self._create_user_data(
                "test_user",
                "lithuanian",
                stats,
                snapshots={"2025-01-14": day1_stats, "2025-01-15": day2_stats},
            )

            result = migrate_user("test_user", "lithuanian")
            self.assertTrue(result)

            # Check snapshots in SQLite
            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")

            self.assertTrue(db.snapshot_exists("2025-01-14"))
            self.assertTrue(db.snapshot_exists("2025-01-15"))

            snapshot = db._get_snapshot("2025-01-15")
            self.assertEqual(snapshot["exposed_words_count"], 1)
            self.assertEqual(snapshot["total_questions_answered"], 10)

    def test_migrate_gzip_snapshots(self):
        """Test that gzip-compressed snapshots are migrated."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word(exposed=True, mc_correct=5)}}
            self._create_user_data("test_user", "lithuanian", stats)

            # Add a gzip snapshot manually
            daily_dir = os.path.join(
                self.test_data_dir, "trakaido", "test_user", "lithuanian", "daily"
            )
            os.makedirs(daily_dir, exist_ok=True)
            gz_data = {"stats": {"w1": _make_word(exposed=True, mc_correct=3)}}
            with gzip.open(
                os.path.join(daily_dir, "2025-01-13_current.json.gz"), "wt"
            ) as f:
                json.dump(gz_data, f)

            result = migrate_user("test_user", "lithuanian")
            self.assertTrue(result)

            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")
            self.assertTrue(db.snapshot_exists("2025-01-13"))

    def test_skip_existing_database(self):
        """Test that existing SQLite databases are skipped without --force."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word()}}
            self._create_user_data("test_user", "lithuanian", stats)

            # First migration succeeds
            self.assertTrue(migrate_user("test_user", "lithuanian"))

            # Second migration without force should skip
            self.assertFalse(migrate_user("test_user", "lithuanian", force=False))

    def test_force_overwrites_existing(self):
        """Test that --force overwrites an existing SQLite database."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word(mc_correct=5)}}
            self._create_user_data("test_user", "lithuanian", stats)

            # First migration
            self.assertTrue(migrate_user("test_user", "lithuanian"))

            # Update flat file
            updated_stats = {
                "stats": {
                    "w1": _make_word(mc_correct=5),
                    "w2": _make_word(mc_correct=10),
                }
            }
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", "test_user", "lithuanian"
            )
            with open(os.path.join(user_dir, "stats.json"), "w") as f:
                json.dump(updated_stats, f)

            # Force migration
            self.assertTrue(migrate_user("test_user", "lithuanian", force=True))

            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")
            loaded = db.get_all_stats()
            self.assertEqual(len(loaded["stats"]), 2)

    def test_dry_run_does_not_create_db(self):
        """Test that dry run mode doesn't create any files."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word()}}
            self._create_user_data("test_user", "lithuanian", stats)

            result = migrate_user("test_user", "lithuanian", dry_run=True)
            self.assertTrue(result)

            db_path = os.path.join(
                self.test_data_dir, "trakaido", "test_user", "lithuanian", "stats.db"
            )
            self.assertFalse(os.path.exists(db_path))

    def test_no_stats_file_skips(self):
        """Test that a user with no stats.json is skipped."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            # Create user dir without stats.json
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", "test_user", "lithuanian"
            )
            os.makedirs(user_dir)

            result = migrate_user("test_user", "lithuanian")
            self.assertFalse(result)

    def test_marked_as_known_preserved(self):
        """Test that markedAsKnown flag is preserved during migration."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            ws = create_empty_word_stats()
            ws["exposed"] = True
            ws["markedAsKnown"] = True
            stats = {"stats": {"w1": ws}}
            self._create_user_data("test_user", "lithuanian", stats)

            self.assertTrue(migrate_user("test_user", "lithuanian"))

            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")
            loaded = db.get_all_stats()
            self.assertTrue(loaded["stats"]["w1"].get("markedAsKnown", False))

    def test_snapshot_newly_exposed_calculation(self):
        """Test that newly_exposed_words is computed correctly across snapshots."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            stats = {"stats": {"w1": _make_word(), "w2": _make_word(), "w3": _make_word()}}

            # Day 1: 1 word exposed, Day 2: 2 words exposed, Day 3: 3 words exposed
            day1 = {"stats": {"w1": _make_word(exposed=True)}}
            day2 = {"stats": {"w1": _make_word(exposed=True), "w2": _make_word(exposed=True)}}
            day3 = {
                "stats": {
                    "w1": _make_word(exposed=True),
                    "w2": _make_word(exposed=True),
                    "w3": _make_word(exposed=True),
                }
            }

            self._create_user_data(
                "test_user",
                "lithuanian",
                stats,
                snapshots={"2025-01-13": day1, "2025-01-14": day2, "2025-01-15": day3},
            )

            self.assertTrue(migrate_user("test_user", "lithuanian"))

            from trakaido.blueprints.stats_sqlite import SqliteStatsDB
            db = SqliteStatsDB("test_user", "lithuanian")

            snap1 = db._get_snapshot("2025-01-13")
            snap2 = db._get_snapshot("2025-01-14")
            snap3 = db._get_snapshot("2025-01-15")

            # Day 1: first snapshot, no previous → newly_exposed = 1 (since prev is 0)
            self.assertEqual(snap1["newly_exposed_words"], 1)
            # Day 2: prev had 1 exposed, now 2 → newly_exposed = 1
            self.assertEqual(snap2["newly_exposed_words"], 1)
            # Day 3: prev had 2 exposed, now 3 → newly_exposed = 1
            self.assertEqual(snap3["newly_exposed_words"], 1)


if __name__ == "__main__":
    unittest.main()
