"""Tests for Trakaido stats storage functions (Priority 1, 2, and 3 coverage)."""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from trakaido.blueprints.userstats import (
    parse_stat_type,
    increment_word_stat,
)
from trakaido.blueprints.stats_schema import (
    create_empty_word_stats,
    validate_and_normalize_word_stats,
    format_stats_json,
    JourneyStats,
    DailyStats,
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
)
from trakaido.blueprints.stats_snapshots import (
    ensure_daily_snapshots,
    calculate_progress_delta,
    calculate_daily_progress,
    calculate_weekly_progress,
    calculate_monthly_progress,
    find_best_baseline,
    compress_previous_day_files,
)
from trakaido.blueprints.date_utils import get_current_day_key


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


# ============================================================================
# Priority 2 Tests
# ============================================================================

class GetStatTypeTotalTests(unittest.TestCase):
    """Test cases for DailyStats.get_stat_type_total() and get_all_stat_totals()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_get_stat_type_total_single_word(self):
        """Test get_stat_type_total with a single word."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            daily_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            daily_stats.load()

            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            word["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 3
            daily_stats.set_word_stats("word1", word)

            # Get totals for this stat type
            totals = daily_stats.get_stat_type_total("directPractice.multipleChoice_englishToTarget")

            self.assertEqual(totals["correct"], 10)
            self.assertEqual(totals["incorrect"], 3)

    def test_get_stat_type_total_multiple_words(self):
        """Test get_stat_type_total aggregates across multiple words."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            daily_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            daily_stats.load()

            # Add multiple words with same stat type
            for i in range(3):
                word = create_empty_word_stats()
                word["exposed"] = True
                word["directPractice"]["typing_targetToEnglish"]["correct"] = 5
                word["directPractice"]["typing_targetToEnglish"]["incorrect"] = 2
                daily_stats.set_word_stats(f"word{i}", word)

            # Get totals
            totals = daily_stats.get_stat_type_total("directPractice.typing_targetToEnglish")

            # Should aggregate: 3 words × (5 correct, 2 incorrect)
            self.assertEqual(totals["correct"], 15)
            self.assertEqual(totals["incorrect"], 6)

    def test_get_stat_type_total_contextual_exposure(self):
        """Test get_stat_type_total with contextual exposure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            daily_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            daily_stats.load()

            word = create_empty_word_stats()
            word["exposed"] = True
            word["contextualExposure"]["sentences"]["correct"] = 7
            word["contextualExposure"]["sentences"]["incorrect"] = 1
            daily_stats.set_word_stats("word1", word)

            totals = daily_stats.get_stat_type_total("contextualExposure.sentences")

            self.assertEqual(totals["correct"], 7)
            self.assertEqual(totals["incorrect"], 1)

    def test_get_stat_type_total_category_choice(self):
        """Test get_stat_type_total with categoryChoice contextual exposure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            daily_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            daily_stats.load()

            word = create_empty_word_stats()
            word["exposed"] = True
            word["contextualExposure"]["categoryChoice"]["correct"] = 3
            word["contextualExposure"]["categoryChoice"]["incorrect"] = 2
            daily_stats.set_word_stats("word1", word)

            totals = daily_stats.get_stat_type_total("contextualExposure.categoryChoice")

            self.assertEqual(totals["correct"], 3)
            self.assertEqual(totals["incorrect"], 2)

    def test_get_all_stat_totals(self):
        """Test get_all_stat_totals returns all activity types."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            daily_stats = DailyStats(self.test_user_id, "2025-01-01", "current", self.test_language)
            daily_stats.load()

            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            word["directPractice"]["typing_targetToEnglish"]["correct"] = 3
            word["contextualExposure"]["sentences"]["correct"] = 2
            word["contextualExposure"]["categoryChoice"]["correct"] = 4
            daily_stats.set_word_stats("word1", word)

            all_totals = daily_stats.get_all_stat_totals()

            # Check that all activity types are present
            self.assertIn("directPractice.multipleChoice_englishToTarget", all_totals)
            self.assertIn("directPractice.typing_targetToEnglish", all_totals)
            self.assertIn("contextualExposure.sentences", all_totals)
            self.assertIn("contextualExposure.categoryChoice", all_totals)

            # Check specific values
            self.assertEqual(all_totals["directPractice.multipleChoice_englishToTarget"]["correct"], 5)
            self.assertEqual(all_totals["directPractice.typing_targetToEnglish"]["correct"], 3)
            self.assertEqual(all_totals["contextualExposure.sentences"]["correct"], 2)
            self.assertEqual(all_totals["contextualExposure.categoryChoice"]["correct"], 4)


class CalculateWeeklyProgressTests(unittest.TestCase):
    """Test cases for calculate_weekly_progress()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_calculate_weekly_progress_structure(self):
        """Test calculate_weekly_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            # Create some journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 10
            journey_stats.set_word_stats("word1", word)
            journey_stats.save()

            result = calculate_weekly_progress(self.test_user_id, self.test_language)

            # Check structure
            self.assertIn("currentDay", result)
            self.assertIn("targetBaselineDay", result)
            self.assertIn("actualBaselineDay", result)
            self.assertIn("progress", result)
            self.assertNotIn("error", result)

    def test_calculate_weekly_progress_with_baseline(self):
        """Test calculate_weekly_progress calculates delta correctly."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            current_day = get_current_day_key()
            week_ago = (datetime.strptime(current_day, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

            # Create baseline from a week ago
            baseline_stats = DailyStats(self.test_user_id, week_ago, "current", self.test_language)
            baseline_stats.load()
            baseline_word = create_empty_word_stats()
            baseline_word["exposed"] = True
            baseline_word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            baseline_stats.set_word_stats("word1", baseline_word)
            baseline_stats.save()

            # Create current stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            current_word = create_empty_word_stats()
            current_word["exposed"] = True
            current_word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 15
            journey_stats.set_word_stats("word1", current_word)
            journey_stats.save()

            # Ensure snapshots
            ensure_daily_snapshots(self.test_user_id, self.test_language)

            result = calculate_weekly_progress(self.test_user_id, self.test_language)

            # Should show progress of 10 (15 - 5)
            progress = result["progress"]
            self.assertEqual(progress["directPractice"]["multipleChoice_englishToTarget"]["correct"], 10)


class CalculateMonthlyProgressTests(unittest.TestCase):
    """Test cases for calculate_monthly_progress()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_calculate_monthly_progress_structure(self):
        """Test calculate_monthly_progress returns expected structure."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            # Create some journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 20
            journey_stats.set_word_stats("word1", word)
            journey_stats.save()

            result = calculate_monthly_progress(self.test_user_id, self.test_language)

            # Check structure
            self.assertIn("currentMonth", result)
            self.assertIn("currentDay", result)
            self.assertIn("targetBaselineDay", result)
            self.assertIn("actualBaselineDay", result)
            self.assertIn("monthlyAggregate", result)
            self.assertIn("dailyData", result)
            self.assertNotIn("error", result)

            # Check dailyData is a list
            self.assertIsInstance(result["dailyData"], list)

            # Check monthlyAggregate has correct structure
            aggregate = result["monthlyAggregate"]
            self.assertIn("directPractice", aggregate)
            self.assertIn("contextualExposure", aggregate)
            self.assertIn("exposed", aggregate)

    def test_calculate_monthly_progress_daily_data(self):
        """Test calculate_monthly_progress includes daily breakdown."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            current_day = get_current_day_key()

            # Create a daily snapshot with some data
            daily_stats = DailyStats(self.test_user_id, current_day, "current", self.test_language)
            daily_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            word["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5
            word["directPractice"]["multipleChoice_englishToTarget"]["incorrect"] = 2
            daily_stats.set_word_stats("word1", word)
            daily_stats.save()

            result = calculate_monthly_progress(self.test_user_id, self.test_language)

            # Check that dailyData includes today
            daily_data = result["dailyData"]
            today_data = next((d for d in daily_data if d["date"] == current_day), None)

            self.assertIsNotNone(today_data)
            self.assertIn("questionsAnswered", today_data)
            self.assertIn("exposedWordsCount", today_data)
            self.assertIn("newlyExposedWords", today_data)

            # Should have 7 questions answered (5 correct + 2 incorrect)
            self.assertEqual(today_data["questionsAnswered"], 7)
            # Should have 1 exposed word
            self.assertEqual(today_data["exposedWordsCount"], 1)


# ============================================================================
# Priority 3 Tests
# ============================================================================

class FindBestBaselineTests(unittest.TestCase):
    """Test cases for find_best_baseline() using mocks."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def test_find_best_baseline_exact_date_exists(self):
        """Test find_best_baseline returns exact target date when it exists."""
        target_day = "2025-01-15"

        # Mock DailyStats to simulate existing data
        with patch('trakaido.blueprints.stats_snapshots.DailyStats') as MockDailyStats:
            mock_instance = MagicMock()
            mock_instance.is_empty.return_value = False
            mock_instance.date = target_day
            MockDailyStats.return_value = mock_instance
            MockDailyStats.exists.return_value = True

            result = find_best_baseline(self.test_user_id, target_day, 7, self.test_language)

            # Should return the exact date
            self.assertEqual(result.date, target_day)
            self.assertFalse(result.is_empty())

    def test_find_best_baseline_finds_yesterday_snapshot(self):
        """Test find_best_baseline finds yesterday snapshot when target doesn't exist."""
        target_day = "2025-01-15"
        fallback_day = "2025-01-16"  # One day after target

        with patch('trakaido.blueprints.stats_snapshots.DailyStats') as MockDailyStats:
            # Target date doesn't exist
            def exists_side_effect(user_id, date, stats_type, language):
                if date == target_day and stats_type == "current":
                    return False
                return True

            MockDailyStats.exists.side_effect = exists_side_effect

            # get_available_dates returns the fallback date
            MockDailyStats.get_available_dates.return_value = [fallback_day]

            # Create mock instance for fallback
            mock_instance = MagicMock()
            mock_instance.is_empty.return_value = False
            mock_instance.date = fallback_day
            MockDailyStats.return_value = mock_instance

            result = find_best_baseline(self.test_user_id, target_day, 7, self.test_language)

            # Should return the fallback date
            self.assertEqual(result.date, fallback_day)

    def test_find_best_baseline_returns_empty_when_no_data(self):
        """Test find_best_baseline returns empty stats when no baseline found."""
        target_day = "2025-01-15"

        with patch('trakaido.blueprints.stats_snapshots.DailyStats') as MockDailyStats:
            MockDailyStats.exists.return_value = False
            MockDailyStats.get_available_dates.return_value = []

            # Create empty mock instance
            mock_instance = MagicMock()
            mock_instance.stats = {"stats": {}}
            mock_instance.is_empty.return_value = True
            mock_instance.date = target_day
            MockDailyStats.return_value = mock_instance

            result = find_best_baseline(self.test_user_id, target_day, 7, self.test_language)

            # Should return empty stats
            self.assertTrue(result.is_empty())


class CompressPreviousDayFilesTests(unittest.TestCase):
    """Test cases for compress_previous_day_files()."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_compress_previous_day_files_compresses_old_files(self):
        """Test compress_previous_day_files compresses files from previous days."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            current_day = get_current_day_key()
            yesterday = (datetime.strptime(current_day, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

            # Create a daily stats file for yesterday
            yesterday_stats = DailyStats(self.test_user_id, yesterday, "current", self.test_language)
            yesterday_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            yesterday_stats.set_word_stats("word1", word)
            yesterday_stats.save()

            # Verify regular file exists
            self.assertTrue(os.path.exists(yesterday_stats.file_path))
            self.assertFalse(os.path.exists(yesterday_stats.gzip_file_path))

            # Compress previous day files
            result = compress_previous_day_files(self.test_user_id, self.test_language)

            self.assertTrue(result)

            # Verify file was compressed
            self.assertFalse(os.path.exists(yesterday_stats.file_path))
            self.assertTrue(os.path.exists(yesterday_stats.gzip_file_path))

    def test_compress_previous_day_files_skips_current_day(self):
        """Test compress_previous_day_files doesn't compress current day files."""
        with patch('constants.DATA_DIR', self.test_data_dir):
            current_day = get_current_day_key()

            # Create a daily stats file for today
            today_stats = DailyStats(self.test_user_id, current_day, "current", self.test_language)
            today_stats.load()
            word = create_empty_word_stats()
            word["exposed"] = True
            today_stats.set_word_stats("word1", word)
            today_stats.save()

            # Compress previous day files (should skip today)
            compress_previous_day_files(self.test_user_id, self.test_language)

            # Today's file should still be uncompressed
            self.assertTrue(os.path.exists(today_stats.file_path))
            self.assertFalse(os.path.exists(today_stats.gzip_file_path))


class FormatStatsJsonTests(unittest.TestCase):
    """Test cases for format_stats_json()."""

    def test_format_stats_json_one_word_per_line(self):
        """Test format_stats_json puts each word on one line."""
        stats = {
            "stats": {
                "word1": {
                    "exposed": True,
                    "directPractice": {
                        "multipleChoice_englishToTarget": {"correct": 5, "incorrect": 2}
                    },
                    "contextualExposure": {
                        "sentences": {"correct": 0, "incorrect": 0}
                    },
                    "practiceHistory": {
                        "lastSeen": 1234567890,
                        "lastCorrectAnswer": None,
                        "lastIncorrectAnswer": None
                    }
                },
                "word2": {
                    "exposed": False,
                    "directPractice": {
                        "typing_targetToEnglish": {"correct": 3, "incorrect": 1}
                    },
                    "contextualExposure": {
                        "sentences": {"correct": 0, "incorrect": 0}
                    },
                    "practiceHistory": {
                        "lastSeen": None,
                        "lastCorrectAnswer": None,
                        "lastIncorrectAnswer": None
                    }
                }
            }
        }

        result = format_stats_json(stats)

        # Should have proper structure
        self.assertIn('"stats": {', result)
        self.assertIn('"word1":', result)
        self.assertIn('"word2":', result)

        # Each word's data should be on one line (count lines with "word")
        word_lines = [line for line in result.split('\n') if '"word' in line]
        self.assertEqual(len(word_lines), 2)

        # Each word line should be valid JSON
        for line in word_lines:
            # Extract the word stats portion
            word_stats_str = line.strip().rstrip(',')
            if ':' in word_stats_str:
                # Parse just the value part
                _, value_part = word_stats_str.split(':', 1)
                # This should be valid JSON
                import json
                parsed = json.loads(value_part.strip())
                self.assertIn("exposed", parsed)

    def test_format_stats_json_empty_stats(self):
        """Test format_stats_json handles empty stats."""
        stats = {"stats": {}}

        result = format_stats_json(stats)

        # Should produce valid JSON
        import json
        parsed = json.loads(result)
        self.assertEqual(parsed, stats)

    def test_format_stats_json_preserves_unicode(self):
        """Test format_stats_json preserves unicode characters."""
        stats = {
            "stats": {
                "lietuvių": {
                    "exposed": True,
                    "directPractice": {
                        "multipleChoice_englishToTarget": {"correct": 1, "incorrect": 0}
                    },
                    "contextualExposure": {
                        "sentences": {"correct": 0, "incorrect": 0}
                    },
                    "practiceHistory": {
                        "lastSeen": None,
                        "lastCorrectAnswer": None,
                        "lastIncorrectAnswer": None
                    }
                }
            }
        }

        result = format_stats_json(stats)

        # Unicode should be preserved (not escaped)
        self.assertIn("lietuvių", result)
        self.assertNotIn("\\u", result)


if __name__ == '__main__':
    unittest.main()
