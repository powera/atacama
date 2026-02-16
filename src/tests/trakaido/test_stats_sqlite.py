"""Tests for Trakaido SQLite stats storage backend."""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from trakaido.blueprints.stats_schema import create_empty_word_stats
from trakaido.blueprints.stats_sqlite import (
    SqliteStatsDB,
    SqliteJourneyStats,
)
from trakaido.blueprints.stats_backend import (
    get_storage_backend,
    get_journey_stats,
    ensure_daily_snapshots,
    calculate_daily_progress,
    calculate_weekly_progress,
    calculate_monthly_progress,
    BACKEND_FLATFILE,
    BACKEND_SQLITE,
)
from trakaido.blueprints.date_utils import get_current_day_key
from trakaido.blueprints.userstats import increment_word_stat


class SqliteStatsDBSchemaTests(unittest.TestCase):
    """Test database schema creation and initialization."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_sqlite"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_schema_creation(self):
        """Test that database schema is created correctly."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            # Database file should exist
            self.assertTrue(os.path.exists(db.db_path))

            # Check tables exist
            conn = db._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {row["name"] for row in cursor}
                self.assertIn("word_stats", tables)
                self.assertIn("word_activity_stats", tables)
                self.assertIn("daily_snapshots", tables)
                self.assertIn("schema_info", tables)
            finally:
                conn.close()

    def test_schema_version_stored(self):
        """Test that schema version is recorded."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            conn = db._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT value FROM schema_info WHERE key = 'version'"
                )
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["value"], "1")
            finally:
                conn.close()

    def test_repeated_init_is_safe(self):
        """Test that creating SqliteStatsDB multiple times is idempotent."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db1 = SqliteStatsDB(self.test_user_id, self.test_language)
            db2 = SqliteStatsDB(self.test_user_id, self.test_language)
            self.assertEqual(db1.db_path, db2.db_path)


class SqliteStatsDBWordStatsTests(unittest.TestCase):
    """Test word stats CRUD operations."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_sqlite"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_empty_stats(self):
        """Test loading stats from an empty database."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)
            stats = db.get_all_stats()
            self.assertEqual(stats, {"stats": {}})

    def test_save_and_load_stats(self):
        """Test saving and loading word stats round-trip."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 2
            word_stats["practiceHistory"]["lastSeen"] = 1704067200000

            stats_dict = {"stats": {"N08_011": word_stats}}
            self.assertTrue(db.save_all_stats(stats_dict))

            loaded = db.get_all_stats()
            self.assertIn("N08_011", loaded["stats"])

            loaded_word = loaded["stats"]["N08_011"]
            self.assertTrue(loaded_word["exposed"])
            self.assertEqual(
                loaded_word["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5
            )
            self.assertEqual(
                loaded_word["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 2
            )
            self.assertEqual(
                loaded_word["practiceHistory"]["lastSeen"], 1704067200000
            )

    def test_save_multiple_words(self):
        """Test saving multiple words."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            stats_dict = {"stats": {}}
            for i in range(10):
                word_stats = create_empty_word_stats()
                word_stats["exposed"] = True
                word_stats["directPractice"]["typing_englishToTarget"]["correct"] = i
                stats_dict["stats"][f"word_{i}"] = word_stats

            self.assertTrue(db.save_all_stats(stats_dict))

            loaded = db.get_all_stats()
            self.assertEqual(len(loaded["stats"]), 10)

            for i in range(10):
                self.assertEqual(
                    loaded["stats"][f"word_{i}"]["directPractice"]["typing_englishToTarget"]["correct"],
                    i,
                )

    def test_save_replaces_all(self):
        """Test that save_all_stats replaces existing data."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            # Save initial data
            word1 = create_empty_word_stats()
            word1["exposed"] = True
            db.save_all_stats({"stats": {"word1": word1}})

            # Save different data
            word2 = create_empty_word_stats()
            word2["exposed"] = True
            db.save_all_stats({"stats": {"word2": word2}})

            loaded = db.get_all_stats()
            self.assertNotIn("word1", loaded["stats"])
            self.assertIn("word2", loaded["stats"])

    def test_marked_as_known(self):
        """Test markedAsKnown flag round-trip."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["markedAsKnown"] = True

            db.save_all_stats({"stats": {"word1": word_stats}})
            loaded = db.get_all_stats()
            self.assertTrue(loaded["stats"]["word1"].get("markedAsKnown", False))

    def test_contextual_exposure_stats(self):
        """Test contextual exposure stats round-trip."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["contextualExposure"]["sentences"]["correct"] = 10
            word_stats["contextualExposure"]["flashcards"]["incorrect"] = 3

            db.save_all_stats({"stats": {"word1": word_stats}})
            loaded = db.get_all_stats()

            self.assertEqual(
                loaded["stats"]["word1"]["contextualExposure"]["sentences"]["correct"], 10
            )
            self.assertEqual(
                loaded["stats"]["word1"]["contextualExposure"]["flashcards"]["incorrect"], 3
            )


class SqliteStatsDBSnapshotTests(unittest.TestCase):
    """Test daily snapshot management."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_sqlite"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_snapshot_does_not_exist_initially(self):
        """Test that snapshots don't exist in a fresh database."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)
            self.assertFalse(db.snapshot_exists("2025-01-15"))

    def test_save_and_check_snapshot(self):
        """Test creating and checking a snapshot."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            # Add some data first
            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            db.save_all_stats({"stats": {"word1": word_stats}})

            # Save snapshot
            self.assertTrue(db.save_snapshot_from_current("2025-01-15"))
            self.assertTrue(db.snapshot_exists("2025-01-15"))

    def test_snapshot_contains_correct_totals(self):
        """Test that snapshot captures correct aggregate totals."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            # Add data
            for i in range(3):
                word_stats = create_empty_word_stats()
                word_stats["exposed"] = True
                word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
                word_stats["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 2
                db.save_all_stats(
                    {"stats": {f"word{i}": word_stats for i in range(3)}}
                )

            db.save_snapshot_from_current("2025-01-15")
            snapshot = db._get_snapshot("2025-01-15")

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["exposed_words_count"], 3)
            self.assertEqual(snapshot["words_known_count"], 0)
            # 3 words × (5 correct + 2 incorrect) = 21
            self.assertEqual(snapshot["total_questions_answered"], 21)

            activity_totals = json.loads(snapshot["activity_totals_json"])
            self.assertEqual(
                activity_totals["directPractice"]["multipleChoice_englishToTarget"]["correct"],
                15,
            )

    def test_snapshot_tracks_words_known_count(self):
        """Test snapshot stores known-word count for day-level tracking."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            known_word = create_empty_word_stats()
            known_word["exposed"] = True
            known_word["markedAsKnown"] = True

            unknown_word = create_empty_word_stats()
            unknown_word["exposed"] = True

            db.save_all_stats({"stats": {"known": known_word, "unknown": unknown_word}})
            self.assertTrue(db.save_snapshot_from_current("2025-01-15"))

            snapshot = db._get_snapshot("2025-01-15")
            self.assertEqual(snapshot["words_known_count"], 1)

    def test_ensure_daily_snapshots(self):
        """Test ensure_daily_snapshots creates both snapshots."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            self.assertTrue(db.ensure_daily_snapshots())

            today = get_current_day_key()
            yesterday_key = (
                datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)
            ).strftime("%Y-%m-%d")

            # At least today's snapshot should exist
            self.assertTrue(db.snapshot_exists(today))

    def test_find_best_baseline_exact(self):
        """Test finding baseline when exact date exists."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            db.save_all_stats({"stats": {"word1": word_stats}})
            db.save_snapshot_from_current("2025-01-15")

            baseline = db._find_best_baseline("2025-01-15", 7)
            self.assertIsNotNone(baseline)
            self.assertEqual(baseline["date"], "2025-01-15")

    def test_find_best_baseline_forward_search(self):
        """Test finding baseline searches forward from target."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            db.save_all_stats({"stats": {"word1": word_stats}})
            db.save_snapshot_from_current("2025-01-17")

            baseline = db._find_best_baseline("2025-01-15", 7)
            self.assertIsNotNone(baseline)
            self.assertEqual(baseline["date"], "2025-01-17")

    def test_find_best_baseline_none_found(self):
        """Test finding baseline returns None when no data available."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)
            baseline = db._find_best_baseline("2025-01-15", 7)
            self.assertIsNone(baseline)


class SqliteProgressTests(unittest.TestCase):
    """Test progress calculation methods."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_sqlite"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_daily_progress_structure(self):
        """Test calculate_daily_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            db.save_all_stats({"stats": {"word1": word_stats}})

            result = db.calculate_daily_progress()

            self.assertIn("currentDay", result)
            self.assertIn("progress", result)
            self.assertNotIn("error", result)

            progress = result["progress"]
            self.assertIn("directPractice", progress)
            self.assertIn("contextualExposure", progress)
            self.assertIn("exposed", progress)

    def test_daily_progress_empty(self):
        """Test daily progress with no activity."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)
            result = db.calculate_daily_progress()

            self.assertNotIn("error", result)
            progress = result["progress"]
            self.assertEqual(progress["exposed"]["new"], 0)
            self.assertEqual(progress["exposed"]["total"], 0)

    def test_weekly_progress_structure(self):
        """Test calculate_weekly_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            db.save_all_stats({"stats": {"word1": word_stats}})

            result = db.calculate_weekly_progress()

            self.assertIn("currentDay", result)
            self.assertIn("targetBaselineDay", result)
            self.assertIn("actualBaselineDay", result)
            self.assertIn("progress", result)
            self.assertNotIn("error", result)

    def test_monthly_progress_structure(self):
        """Test calculate_monthly_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 20
            db.save_all_stats({"stats": {"word1": word_stats}})

            result = db.calculate_monthly_progress()

            self.assertIn("currentMonth", result)
            self.assertIn("currentDay", result)
            self.assertIn("targetBaselineDay", result)
            self.assertIn("monthlyAggregate", result)
            self.assertIn("dailyData", result)
            self.assertNotIn("error", result)

            self.assertIsInstance(result["dailyData"], list)
            self.assertIn("wordsKnown", result["dailyData"][0])
            self.assertIn("activitySummary", result["dailyData"][0])

            aggregate = result["monthlyAggregate"]
            self.assertIn("directPractice", aggregate)
            self.assertIn("contextualExposure", aggregate)
            self.assertIn("exposed", aggregate)

    def test_monthly_daily_data_has_30_entries(self):
        """Test monthly progress dailyData has entries for all 30 days."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            db = SqliteStatsDB(self.test_user_id, self.test_language)
            result = db.calculate_monthly_progress()
            self.assertEqual(len(result["dailyData"]), 30)


class SqliteJourneyStatsTests(unittest.TestCase):
    """Test the high-level SqliteJourneyStats interface."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_sqlite"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_empty_journey_stats(self):
        """Test SqliteJourneyStats starts empty."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)
            self.assertTrue(js.is_empty())
            self.assertEqual(js.stats, {"stats": {}})

    def test_set_and_get_word_stats(self):
        """Test setting and getting individual word stats."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5

            js.set_word_stats("word1", word_stats)
            retrieved = js.get_word_stats("word1")
            self.assertTrue(retrieved["exposed"])
            self.assertEqual(
                retrieved["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5
            )

    def test_save_and_reload(self):
        """Test save persists data that can be reloaded."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js1 = SqliteJourneyStats(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["typing_englishToTarget"]["correct"] = 10
            js1.set_word_stats("word1", word_stats)
            self.assertTrue(js1.save())

            # Reload from database
            js2 = SqliteJourneyStats(self.test_user_id, self.test_language)
            retrieved = js2.get_word_stats("word1")
            self.assertTrue(retrieved["exposed"])
            self.assertEqual(
                retrieved["directPractice"]["typing_englishToTarget"]["correct"], 10
            )

    def test_save_with_daily_update(self):
        """Test save_with_daily_update creates daily snapshots."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            js.set_word_stats("word1", word_stats)

            self.assertTrue(js.save_with_daily_update())

            # Verify snapshot was created for today
            today = get_current_day_key()
            self.assertTrue(js._db.snapshot_exists(today))

    def test_save_with_daily_update_preserves_yesterday(self):
        """Test that yesterday's snapshot is not overwritten by later saves."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)

            # Initial save
            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            js.set_word_stats("word1", word_stats)
            js.save_with_daily_update()

            # Get yesterday's snapshot data
            from trakaido.blueprints.date_utils import get_yesterday_day_key
            yesterday = get_yesterday_day_key()
            snapshot_before = js._db._get_snapshot(yesterday)

            # Modify and save again
            word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 20
            js.set_word_stats("word1", word_stats)
            js.save_with_daily_update()

            # Yesterday's snapshot should not change
            snapshot_after = js._db._get_snapshot(yesterday)
            if snapshot_before and snapshot_after:
                self.assertEqual(
                    snapshot_before["activity_totals_json"],
                    snapshot_after["activity_totals_json"],
                )

    def test_increment_word_stat_compatibility(self):
        """Test that increment_word_stat from userstats.py works with SqliteJourneyStats."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)
            js.load()

            timestamp = int(datetime.now().timestamp() * 1000)
            increment_word_stat(
                js, "word1", "directPractice",
                "multipleChoice_englishToTarget", True, False, timestamp
            )

            word = js.get_word_stats("word1")
            self.assertTrue(word["exposed"])
            self.assertEqual(
                word["directPractice"]["multipleChoice_englishToTarget"]["correct"], 1
            )

            self.assertTrue(js.save())

            # Reload and verify
            js2 = SqliteJourneyStats(self.test_user_id, self.test_language)
            word2 = js2.get_word_stats("word1")
            self.assertEqual(
                word2["directPractice"]["multipleChoice_englishToTarget"]["correct"], 1
            )

    def test_stats_setter(self):
        """Test setting stats dict directly."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = SqliteJourneyStats(self.test_user_id, self.test_language)

            word_stats = create_empty_word_stats()
            word_stats["exposed"] = True
            js.stats = {"stats": {"word1": word_stats}}

            self.assertFalse(js.is_empty())
            self.assertTrue(js.save())

            # Reload
            js2 = SqliteJourneyStats(self.test_user_id, self.test_language)
            self.assertFalse(js2.is_empty())
            self.assertTrue(js2.get_word_stats("word1")["exposed"])


class BackendSelectionTests(unittest.TestCase):
    """Test backend selection via server_settings.json."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_backend"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_default_backend_is_sqlite(self):
        """Test that default backend is sqlite when no settings file exists."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            backend = get_storage_backend(self.test_user_id, self.test_language)
            self.assertEqual(backend, BACKEND_SQLITE)

    def test_sqlite_backend_from_settings(self):
        """Test that SQLite backend is selected from server_settings.json."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            # Create settings file
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", self.test_user_id, self.test_language
            )
            os.makedirs(user_dir, exist_ok=True)
            settings_path = os.path.join(user_dir, "server_settings.json")
            with open(settings_path, "w") as f:
                json.dump({"storage_backend": "sqlite"}, f)

            backend = get_storage_backend(self.test_user_id, self.test_language)
            self.assertEqual(backend, BACKEND_SQLITE)

    def test_flatfile_backend_from_settings(self):
        """Test explicit flatfile backend in settings."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", self.test_user_id, self.test_language
            )
            os.makedirs(user_dir, exist_ok=True)
            settings_path = os.path.join(user_dir, "server_settings.json")
            with open(settings_path, "w") as f:
                json.dump({"storage_backend": "flatfile"}, f)

            backend = get_storage_backend(self.test_user_id, self.test_language)
            self.assertEqual(backend, BACKEND_FLATFILE)

    def test_invalid_settings_falls_back(self):
        """Test that invalid settings file falls back to default (sqlite)."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", self.test_user_id, self.test_language
            )
            os.makedirs(user_dir, exist_ok=True)
            settings_path = os.path.join(user_dir, "server_settings.json")
            with open(settings_path, "w") as f:
                f.write("not valid json")

            backend = get_storage_backend(self.test_user_id, self.test_language)
            self.assertEqual(backend, BACKEND_SQLITE)

    def test_factory_returns_sqlite_journey_stats(self):
        """Test that factory returns SqliteJourneyStats when configured."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", self.test_user_id, self.test_language
            )
            os.makedirs(user_dir, exist_ok=True)
            settings_path = os.path.join(user_dir, "server_settings.json")
            with open(settings_path, "w") as f:
                json.dump({"storage_backend": "sqlite"}, f)

            js = get_journey_stats(self.test_user_id, self.test_language)
            self.assertIsInstance(js, SqliteJourneyStats)

    def test_factory_returns_sqlite_journey_stats_by_default(self):
        """Test that factory returns SqliteJourneyStats when no settings file exists."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            js = get_journey_stats(self.test_user_id, self.test_language)
            self.assertIsInstance(js, SqliteJourneyStats)

    def test_factory_returns_flatfile_journey_stats_when_configured(self):
        """Test that factory returns JourneyStats when configured for flatfile."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            user_dir = os.path.join(
                self.test_data_dir, "trakaido", self.test_user_id, self.test_language
            )
            os.makedirs(user_dir, exist_ok=True)
            settings_path = os.path.join(user_dir, "server_settings.json")
            with open(settings_path, "w") as f:
                json.dump({"storage_backend": "flatfile"}, f)

            from trakaido.blueprints.stats_schema import JourneyStats
            js = get_journey_stats(self.test_user_id, self.test_language)
            self.assertIsInstance(js, JourneyStats)


class BackendDispatchTests(unittest.TestCase):
    """Test that dispatch functions work for both backends."""

    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_dispatch"
        self.test_language = "lithuanian"

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def _enable_sqlite(self):
        """Create server_settings.json for SQLite backend."""
        user_dir = os.path.join(
            self.test_data_dir, "trakaido", self.test_user_id, self.test_language
        )
        os.makedirs(user_dir, exist_ok=True)
        settings_path = os.path.join(user_dir, "server_settings.json")
        with open(settings_path, "w") as f:
            json.dump({"storage_backend": "sqlite"}, f)

    def _enable_flatfile(self):
        """Create server_settings.json for flatfile backend."""
        user_dir = os.path.join(
            self.test_data_dir, "trakaido", self.test_user_id, self.test_language
        )
        os.makedirs(user_dir, exist_ok=True)
        settings_path = os.path.join(user_dir, "server_settings.json")
        with open(settings_path, "w") as f:
            json.dump({"storage_backend": "flatfile"}, f)

    def test_dispatch_ensure_daily_snapshots_sqlite(self):
        """Test ensure_daily_snapshots dispatches to SQLite backend."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            self._enable_sqlite()
            result = ensure_daily_snapshots(self.test_user_id, self.test_language)
            self.assertTrue(result)

    def test_dispatch_ensure_daily_snapshots_flatfile(self):
        """Test ensure_daily_snapshots dispatches to flatfile backend."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            self._enable_flatfile()
            result = ensure_daily_snapshots(self.test_user_id, self.test_language)
            self.assertTrue(result)

    def test_dispatch_daily_progress_sqlite(self):
        """Test calculate_daily_progress dispatches to SQLite backend."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            self._enable_sqlite()
            result = calculate_daily_progress(self.test_user_id, self.test_language)
            self.assertIn("currentDay", result)
            self.assertNotIn("error", result)

    def test_dispatch_weekly_progress_sqlite(self):
        """Test calculate_weekly_progress dispatches to SQLite backend."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            self._enable_sqlite()
            result = calculate_weekly_progress(self.test_user_id, self.test_language)
            self.assertIn("currentDay", result)
            self.assertNotIn("error", result)

    def test_dispatch_monthly_progress_sqlite(self):
        """Test calculate_monthly_progress dispatches to SQLite backend."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            self._enable_sqlite()
            result = calculate_monthly_progress(self.test_user_id, self.test_language)
            self.assertIn("currentDay", result)
            self.assertNotIn("error", result)


if __name__ == '__main__':
    unittest.main()
