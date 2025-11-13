"""Tests for Trakaido stats storage functions (Priority 1 coverage)."""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch
from datetime import datetime, timezone

from web.blueprints.trakaido.userstats import (
    parse_stat_type,
    increment_word_stat,
)
from web.blueprints.trakaido.stats_schema import (
    create_empty_word_stats,
    validate_and_normalize_word_stats,
    JourneyStats,
    DailyStats,
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
)
from web.blueprints.trakaido.stats_snapshots import (
    ensure_daily_snapshots,
    calculate_progress_delta,
    calculate_daily_progress,
)
from web.blueprints.trakaido.date_utils import get_current_day_key


class SaveWithDailyUpdateTests(unittest.TestCase):
    """Test cases for JourneyStats.save_with_daily_update()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_save_with_daily_update_creates_snapshots(self):
        """Test save_with_daily_update creates daily snapshots."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create journey stats with some data
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            journey_stats.set_word_stats("test_word", test_word_stats)

            # Save with daily update
            result = journey_stats.save_with_daily_update()

            self.assertTrue(result)

            # Verify journey stats file was created
            self.assertTrue(os.path.exists(journey_stats.file_path))

            # Verify daily snapshots were created
            current_day = get_current_day_key()
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "current", self.test_language))
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "yesterday", self.test_language))

    def test_save_with_daily_update_updates_current_snapshot(self):
        """Test save_with_daily_update updates the current snapshot."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create journey stats and save with initial data
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save_with_daily_update()

            # Modify stats
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save_with_daily_update()

            # Verify current snapshot has updated data
            current_day = get_current_day_key()
            current_snapshot = DailyStats(self.test_user_id, current_day, "current", self.test_language)
            current_snapshot.load()

            snapshot_word_stats = current_snapshot.get_word_stats("test_word")
            self.assertEqual(snapshot_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 10)

    def test_save_with_daily_update_preserves_yesterday_snapshot(self):
        """Test save_with_daily_update doesn't overwrite yesterday snapshot."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create initial journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save_with_daily_update()

            # Get yesterday snapshot stats
            current_day = get_current_day_key()
            yesterday_snapshot = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot.load()
            initial_yesterday_stats = yesterday_snapshot.get_word_stats("test_word")

            # Modify and save again
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save_with_daily_update()

            # Verify yesterday snapshot was NOT changed (should still be 5)
            yesterday_snapshot2 = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot2.load()
            final_yesterday_stats = yesterday_snapshot2.get_word_stats("test_word")

            self.assertEqual(final_yesterday_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5)


class EnsureDailySnapshotsTests(unittest.TestCase):
    """Test cases for ensure_daily_snapshots()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_ensure_daily_snapshots_creates_both_snapshots(self):
        """Test ensure_daily_snapshots creates both yesterday and current snapshots."""
        with patch('constants.DATA_DIR', self.test_data_dir):


            # Create some journey stats first
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save()

            # Ensure snapshots
            result = ensure_daily_snapshots(self.test_user_id, self.test_language)

            self.assertTrue(result)

            # Verify both snapshots exist
            current_day = get_current_day_key()
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "current", self.test_language))
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "yesterday", self.test_language))

    def test_ensure_daily_snapshots_with_empty_journey_stats(self):
        """Test ensure_daily_snapshots works with empty journey stats."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Don't create any journey stats, just call ensure
            result = ensure_daily_snapshots(self.test_user_id, self.test_language)

            self.assertTrue(result)

            # Snapshots should exist but be empty
            current_day = get_current_day_key()
            yesterday_snapshot = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot.load()
            self.assertTrue(yesterday_snapshot.is_empty())

            current_snapshot = DailyStats(self.test_user_id, current_day, "current", self.test_language)
            current_snapshot.load()
            self.assertTrue(current_snapshot.is_empty())

    def test_ensure_daily_snapshots_doesnt_overwrite_existing(self):
        """Test ensure_daily_snapshots doesn't overwrite existing yesterday snapshot."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            current_day = get_current_day_key()

            # Create yesterday snapshot with specific data
            yesterday_snapshot = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot.load()
            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            yesterday_snapshot.set_word_stats("test_word", test_word_stats)
            yesterday_snapshot.save()

            # Create journey stats with different data
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            different_stats = create_empty_word_stats()
            different_stats["exposed"] = True
            different_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            journey_stats.set_word_stats("test_word", different_stats)
            journey_stats.save()

            # Call ensure_daily_snapshots
            ensure_daily_snapshots(self.test_user_id, self.test_language)

            # Yesterday snapshot should still have original value (5, not 10)
            yesterday_snapshot2 = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot2.load()
            word_stats = yesterday_snapshot2.get_word_stats("test_word")
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5)

    def test_ensure_daily_snapshots_copies_journey_stats(self):
        """Test ensure_daily_snapshots copies data from journey stats."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create journey stats with specific data
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 7
            journey_stats.set_word_stats("test_word", test_word_stats)
            journey_stats.save()

            # Ensure snapshots
            ensure_daily_snapshots(self.test_user_id, self.test_language)

            # Both snapshots should have the journey stats data
            current_day = get_current_day_key()

            yesterday_snapshot = DailyStats(self.test_user_id, current_day, "yesterday", self.test_language)
            yesterday_snapshot.load()
            self.assertEqual(
                yesterday_snapshot.get_word_stats("test_word")["directPractice"]["multipleChoice_englishToTarget"]["correct"],
                7
            )

            current_snapshot = DailyStats(self.test_user_id, current_day, "current", self.test_language)
            current_snapshot.load()
            self.assertEqual(
                current_snapshot.get_word_stats("test_word")["directPractice"]["multipleChoice_englishToTarget"]["correct"],
                7
            )


class CalculateProgressDeltaTests(unittest.TestCase):
    """Test cases for calculate_progress_delta()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_calculate_progress_delta_with_new_words(self):
        """Test calculate_progress_delta correctly counts new words."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create baseline (empty)
            baseline_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            baseline_stats.load()

            # Create current with one exposed word
            current_stats = DailyStats(self.test_user_id, "2025-01-02", "current", self.test_language)
            current_stats.load()
            test_word = create_empty_word_stats()
            test_word["exposed"] = True
            test_word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            current_stats.set_word_stats("word1", test_word)

            # Calculate delta
            delta = calculate_progress_delta(current_stats, baseline_stats)

            # Should have 1 new exposed word
            self.assertEqual(delta["exposed"]["new"], 1)
            self.assertEqual(delta["exposed"]["total"], 1)
            # Should have 5 correct answers
            self.assertEqual(delta["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5)

    def test_calculate_progress_delta_with_incremented_stats(self):
        """Test calculate_progress_delta correctly calculates increments."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create baseline with some stats
            baseline_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            baseline_stats.load()
            baseline_word = create_empty_word_stats()
            baseline_word["exposed"] = True
            baseline_word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            baseline_word["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 2
            baseline_stats.set_word_stats("word1", baseline_word)

            # Create current with incremented stats
            current_stats = DailyStats(self.test_user_id, "2025-01-02", "current", self.test_language)
            current_stats.load()
            current_word = create_empty_word_stats()
            current_word["exposed"] = True
            current_word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            current_word["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 5
            current_stats.set_word_stats("word1", current_word)

            # Calculate delta
            delta = calculate_progress_delta(current_stats, baseline_stats)

            # Should have 0 new words (word was already exposed in baseline)
            self.assertEqual(delta["exposed"]["new"], 0)
            self.assertEqual(delta["exposed"]["total"], 1)
            # Should have delta of 5 correct, 3 incorrect
            self.assertEqual(delta["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5)
            self.assertEqual(delta["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 3)

    def test_calculate_progress_delta_multiple_words(self):
        """Test calculate_progress_delta aggregates across multiple words."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create baseline
            baseline_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            baseline_stats.load()

            # Create current with multiple words
            current_stats = DailyStats(self.test_user_id, "2025-01-02", "current", self.test_language)
            current_stats.load()

            for i in range(3):
                word = create_empty_word_stats()
                word["exposed"] = True
                word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
                current_stats.set_word_stats(f"word{i}", word)

            # Calculate delta
            delta = calculate_progress_delta(current_stats, baseline_stats)

            # Should aggregate across all 3 words
            self.assertEqual(delta["exposed"]["new"], 3)
            self.assertEqual(delta["exposed"]["total"], 3)
            self.assertEqual(delta["directPractice"]["multipleChoice_englishToTarget"]["correct"], 15)


class CalculateDailyProgressTests(unittest.TestCase):
    """Test cases for calculate_daily_progress()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_calculate_daily_progress_successful(self):
        """Test calculate_daily_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Create journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            journey_stats.set_word_stats("word1", word)
            journey_stats.save()

            # Calculate daily progress
            result = calculate_daily_progress(self.test_user_id, self.test_language)

            # Check structure
            self.assertIn("currentDay", result)
            self.assertIn("progress", result)
            self.assertNotIn("error", result)

            # Check progress structure
            progress = result["progress"]
            self.assertIn("directPractice", progress)
            self.assertIn("contextualExposure", progress)
            self.assertIn("exposed", progress)

    def test_calculate_daily_progress_with_empty_stats(self):
        """Test calculate_daily_progress with no activity."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            # Calculate without any stats
            result = calculate_daily_progress(self.test_user_id, self.test_language)

            # Should succeed with zero progress
            self.assertNotIn("error", result)
            progress = result["progress"]
            self.assertEqual(progress["exposed"]["new"], 0)
            self.assertEqual(progress["exposed"]["total"], 0)

    def test_calculate_daily_progress_ensures_snapshots(self):
        """Test calculate_daily_progress creates snapshots if missing."""
        with patch('constants.DATA_DIR', self.test_data_dir):

            current_day = get_current_day_key()

            # Snapshots shouldn't exist yet
            self.assertFalse(DailyStats.exists(self.test_user_id, current_day, "current", self.test_language))
            self.assertFalse(DailyStats.exists(self.test_user_id, current_day, "yesterday", self.test_language))

            # Calculate daily progress
            calculate_daily_progress(self.test_user_id, self.test_language)

            # Snapshots should now exist
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "current", self.test_language))
            self.assertTrue(DailyStats.exists(self.test_user_id, current_day, "yesterday", self.test_language))


if __name__ == '__main__':
    unittest.main()
