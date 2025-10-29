"""Tests for userstats module."""

import unittest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone

from web.blueprints.trakaido.userstats import (
    create_empty_word_stats,
    is_old_schema,
    migrate_old_to_new_schema,
    validate_and_normalize_word_stats,
    parse_stat_type,
    increment_word_stat,
    JourneyStats,
    DailyStats,
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
    OLD_STAT_TYPES
)


class UserStatsSchemaTests(unittest.TestCase):
    """Test cases for schema creation and validation."""

    def test_create_empty_word_stats_structure(self):
        """Test create_empty_word_stats creates correct structure."""
        stats = create_empty_word_stats()

        # Check top-level keys
        self.assertIn("exposed", stats)
        self.assertIn("directPractice", stats)
        self.assertIn("contextualExposure", stats)
        self.assertIn("practiceHistory", stats)

        # Check initial values
        self.assertFalse(stats["exposed"])

        # Check directPractice has all activity types
        for activity in DIRECT_PRACTICE_TYPES:
            self.assertIn(activity, stats["directPractice"])
            self.assertEqual(stats["directPractice"][activity], {"correct": 0, "incorrect": 0})

        # Check contextualExposure
        self.assertIn("sentences", stats["contextualExposure"])
        self.assertEqual(stats["contextualExposure"]["sentences"], {"correct": 0, "incorrect": 0})

        # Check practiceHistory
        self.assertIsNone(stats["practiceHistory"]["lastSeen"])
        self.assertIsNone(stats["practiceHistory"]["lastCorrectAnswer"])
        self.assertIsNone(stats["practiceHistory"]["lastIncorrectAnswer"])

    def test_is_old_schema_detects_old_format(self):
        """Test is_old_schema correctly identifies old schema."""
        # Old schema with old stat types
        old_stats = {
            "multipleChoice": {"correct": 5, "incorrect": 2},
            "exposed": True
        }
        self.assertTrue(is_old_schema(old_stats))

        # Old schema with old meta types
        old_stats_meta = {
            "lastSeen": 1234567890,
            "exposed": True
        }
        self.assertTrue(is_old_schema(old_stats_meta))

    def test_is_old_schema_recognizes_new_format(self):
        """Test is_old_schema correctly identifies new schema."""
        new_stats = create_empty_word_stats()
        self.assertFalse(is_old_schema(new_stats))

    def test_migrate_old_to_new_schema(self):
        """Test migrate_old_to_new_schema converts correctly."""
        old_stats = {
            "exposed": True,
            "multipleChoice": {"correct": 5, "incorrect": 2},
            "listeningEasy": {"correct": 3, "incorrect": 1},
            "listeningHard": {"correct": 2, "incorrect": 0},
            "typing": {"correct": 4, "incorrect": 3},
            "blitz": {"correct": 10, "incorrect": 5},
            "sentences": {"correct": 7, "incorrect": 2},
            "lastSeen": 1234567890,
            "lastCorrectAnswer": 1234567891,
            "lastIncorrectAnswer": 1234567892,
            "markedAsKnown": True
        }

        new_stats = migrate_old_to_new_schema(old_stats)

        # Check structure
        self.assertTrue(new_stats["exposed"])
        self.assertTrue(new_stats["markedAsKnown"])

        # Check migrations to target->english direction
        self.assertEqual(
            new_stats["directPractice"]["multipleChoice_targetToEnglish"],
            {"correct": 5, "incorrect": 2}
        )
        self.assertEqual(
            new_stats["directPractice"]["listening_targetAudioToTarget"],
            {"correct": 3, "incorrect": 1}
        )
        self.assertEqual(
            new_stats["directPractice"]["listening_targetAudioToEnglish"],
            {"correct": 2, "incorrect": 0}
        )
        self.assertEqual(
            new_stats["directPractice"]["typing_targetToEnglish"],
            {"correct": 4, "incorrect": 3}
        )
        self.assertEqual(
            new_stats["directPractice"]["blitz_targetToEnglish"],
            {"correct": 10, "incorrect": 5}
        )
        self.assertEqual(
            new_stats["contextualExposure"]["sentences"],
            {"correct": 7, "incorrect": 2}
        )

        # Check timestamps
        self.assertEqual(new_stats["practiceHistory"]["lastSeen"], 1234567890)
        self.assertEqual(new_stats["practiceHistory"]["lastCorrectAnswer"], 1234567891)
        self.assertEqual(new_stats["practiceHistory"]["lastIncorrectAnswer"], 1234567892)

    def test_validate_and_normalize_word_stats_with_old_schema(self):
        """Test validate_and_normalize_word_stats migrates old schema."""
        old_stats = {
            "exposed": True,
            "multipleChoice": {"correct": 5, "incorrect": 2}
        }

        normalized = validate_and_normalize_word_stats(old_stats)

        # Should be migrated to new schema
        self.assertFalse(is_old_schema(normalized))
        self.assertIn("directPractice", normalized)
        self.assertEqual(
            normalized["directPractice"]["multipleChoice_targetToEnglish"],
            {"correct": 5, "incorrect": 2}
        )

    def test_validate_and_normalize_word_stats_filters_invalid_data(self):
        """Test validate_and_normalize_word_stats filters out invalid values."""
        invalid_stats = {
            "exposed": True,
            "directPractice": {
                "multipleChoice_englishToTarget": {"correct": 5, "incorrect": 2},
                "invalid_activity": {"correct": 1, "incorrect": 1}  # Should be filtered
            },
            "invalidKey": "should be removed"
        }

        normalized = validate_and_normalize_word_stats(invalid_stats)

        # Check valid data is preserved
        self.assertTrue(normalized["exposed"])
        self.assertEqual(
            normalized["directPractice"]["multipleChoice_englishToTarget"],
            {"correct": 5, "incorrect": 2}
        )

        # Check invalid data is removed
        self.assertNotIn("invalidKey", normalized)
        self.assertNotIn("invalid_activity", normalized["directPractice"])

    def test_validate_and_normalize_word_stats_handles_negative_values(self):
        """Test validate_and_normalize_word_stats filters negative values."""
        invalid_stats = {
            "exposed": True,
            "directPractice": {
                "multipleChoice_englishToTarget": {"correct": -5, "incorrect": 2}
            }
        }

        normalized = validate_and_normalize_word_stats(invalid_stats)

        # Negative values should be reset to 0
        self.assertEqual(
            normalized["directPractice"]["multipleChoice_englishToTarget"],
            {"correct": 0, "incorrect": 0}
        )


class ParseStatTypeTests(unittest.TestCase):
    """Test cases for parse_stat_type function."""

    def test_parse_stat_type_new_format_direct_practice(self):
        """Test parse_stat_type with new format direct practice."""
        category, activity, is_contextual = parse_stat_type("directPractice.multipleChoice_englishToTarget")

        self.assertEqual(category, "directPractice")
        self.assertEqual(activity, "multipleChoice_englishToTarget")
        self.assertFalse(is_contextual)

    def test_parse_stat_type_new_format_contextual(self):
        """Test parse_stat_type with new format contextual exposure."""
        category, activity, is_contextual = parse_stat_type("contextualExposure.sentences")

        self.assertEqual(category, "contextualExposure")
        self.assertEqual(activity, "sentences")
        self.assertTrue(is_contextual)

    def test_parse_stat_type_old_format_multiple_choice(self):
        """Test parse_stat_type with old format multipleChoice."""
        category, activity, is_contextual = parse_stat_type("multipleChoice")

        self.assertEqual(category, "directPractice")
        self.assertEqual(activity, "multipleChoice_targetToEnglish")
        self.assertFalse(is_contextual)

    def test_parse_stat_type_old_format_sentences(self):
        """Test parse_stat_type with old format sentences."""
        category, activity, is_contextual = parse_stat_type("sentences")

        self.assertEqual(category, "contextualExposure")
        self.assertEqual(activity, "sentences")
        self.assertTrue(is_contextual)

    def test_parse_stat_type_old_format_listening(self):
        """Test parse_stat_type with old format listening types."""
        # listeningEasy -> listening_targetAudioToTarget
        category, activity, is_contextual = parse_stat_type("listeningEasy")
        self.assertEqual(category, "directPractice")
        self.assertEqual(activity, "listening_targetAudioToTarget")
        self.assertFalse(is_contextual)

        # listeningHard -> listening_targetAudioToEnglish
        category, activity, is_contextual = parse_stat_type("listeningHard")
        self.assertEqual(category, "directPractice")
        self.assertEqual(activity, "listening_targetAudioToEnglish")
        self.assertFalse(is_contextual)

    def test_parse_stat_type_invalid_category(self):
        """Test parse_stat_type raises error for invalid category."""
        with self.assertRaises(ValueError) as context:
            parse_stat_type("invalidCategory.someActivity")

        self.assertIn("Invalid category", str(context.exception))

    def test_parse_stat_type_invalid_activity(self):
        """Test parse_stat_type raises error for invalid activity."""
        with self.assertRaises(ValueError) as context:
            parse_stat_type("directPractice.invalidActivity")

        self.assertIn("Invalid direct practice type", str(context.exception))

    def test_parse_stat_type_invalid_stat_type(self):
        """Test parse_stat_type raises error for completely invalid type."""
        with self.assertRaises(ValueError) as context:
            parse_stat_type("completelyInvalid")

        self.assertIn("Invalid stat type", str(context.exception))


class IncrementWordStatTests(unittest.TestCase):
    """Test cases for increment_word_stat function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_increment_word_stat_creates_new_word(self):
        """Test increment_word_stat creates new word stats if they don't exist."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            word_key = "test_word"
            current_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

            # Increment a word that doesn't exist yet
            word_stats = increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                True,  # correct
                False,  # not contextual
                current_timestamp
            )

            # Verify word was created and incremented
            self.assertTrue(word_stats["exposed"])
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 1)
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 0)
            self.assertEqual(word_stats["practiceHistory"]["lastSeen"], current_timestamp)
            self.assertEqual(word_stats["practiceHistory"]["lastCorrectAnswer"], current_timestamp)

    def test_increment_word_stat_increments_correct(self):
        """Test increment_word_stat increments correct counter."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            word_key = "test_word"
            current_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

            # Increment correct twice
            increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                True,
                False,
                current_timestamp
            )
            word_stats = increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                True,
                False,
                current_timestamp + 1000
            )

            # Verify correct counter is incremented
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 2)
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 0)

    def test_increment_word_stat_increments_incorrect(self):
        """Test increment_word_stat increments incorrect counter."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            word_key = "test_word"
            current_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

            # Increment incorrect
            word_stats = increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                False,  # incorrect
                False,
                current_timestamp
            )

            # Verify incorrect counter is incremented
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 0)
            self.assertEqual(word_stats["directPractice"]["multipleChoice_englishToTarget"]["incorrect"], 1)
            self.assertEqual(word_stats["practiceHistory"]["lastIncorrectAnswer"], current_timestamp)

    def test_increment_word_stat_contextual_exposure(self):
        """Test increment_word_stat handles contextual exposure correctly."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            word_key = "test_word"
            current_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

            # Increment contextual exposure
            word_stats = increment_word_stat(
                journey_stats,
                word_key,
                "contextualExposure",
                "sentences",
                True,
                True,  # is_contextual
                current_timestamp
            )

            # Verify contextual exposure is incremented
            self.assertEqual(word_stats["contextualExposure"]["sentences"]["correct"], 1)
            self.assertEqual(word_stats["practiceHistory"]["lastSeen"], current_timestamp)
            # For contextual exposure, lastCorrectAnswer should NOT be updated
            self.assertIsNone(word_stats["practiceHistory"]["lastCorrectAnswer"])

    def test_increment_word_stat_updates_timestamps(self):
        """Test increment_word_stat updates timestamps correctly."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            word_key = "test_word"
            timestamp1 = 1000000
            timestamp2 = 2000000

            # First increment (correct)
            increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                True,
                False,
                timestamp1
            )

            # Second increment (incorrect)
            word_stats = increment_word_stat(
                journey_stats,
                word_key,
                "directPractice",
                "multipleChoice_englishToTarget",
                False,
                False,
                timestamp2
            )

            # Verify timestamps are updated
            self.assertEqual(word_stats["practiceHistory"]["lastSeen"], timestamp2)
            self.assertEqual(word_stats["practiceHistory"]["lastCorrectAnswer"], timestamp1)
            self.assertEqual(word_stats["practiceHistory"]["lastIncorrectAnswer"], timestamp2)


class JourneyStatsTests(unittest.TestCase):
    """Test cases for JourneyStats class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_journey_stats_file_path(self):
        """Test JourneyStats generates correct file path."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)

            expected_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "stats.json"
            )
            self.assertEqual(journey_stats.file_path, expected_path)

    def test_journey_stats_save_and_load(self):
        """Test JourneyStats can save and load data."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create and save journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            test_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"] = 5

            journey_stats.set_word_stats("test_word", test_word_stats)
            self.assertTrue(journey_stats.save())

            # Load journey stats in new instance
            journey_stats2 = JourneyStats(self.test_user_id, self.test_language)
            journey_stats2.load()

            loaded_word_stats = journey_stats2.get_word_stats("test_word")
            self.assertTrue(loaded_word_stats["exposed"])
            self.assertEqual(loaded_word_stats["directPractice"]["multipleChoice_englishToTarget"]["correct"], 5)

    def test_journey_stats_is_empty(self):
        """Test JourneyStats.is_empty returns correct value."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            # Should be empty initially
            self.assertTrue(journey_stats.is_empty())

            # Add a word
            journey_stats.set_word_stats("test_word", create_empty_word_stats())

            # Should no longer be empty
            self.assertFalse(journey_stats.is_empty())

    def test_journey_stats_filters_invalid_on_load(self):
        """Test JourneyStats filters invalid data on load."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create a file with invalid data
            file_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "stats.json"
            )
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            invalid_data = {
                "stats": {
                    "word1": {
                        "exposed": True,
                        "multipleChoice": {"correct": 5, "incorrect": 2},  # Old schema
                        "invalidKey": "should be removed"
                    }
                }
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(invalid_data, f)

            # Load journey stats
            journey_stats = JourneyStats(self.test_user_id, self.test_language)
            journey_stats.load()

            # Verify data was migrated and filtered
            word_stats = journey_stats.get_word_stats("word1")
            self.assertIn("directPractice", word_stats)
            self.assertNotIn("multipleChoice", word_stats)
            self.assertNotIn("invalidKey", word_stats)


class DailyStatsTests(unittest.TestCase):
    """Test cases for DailyStats class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"
        self.test_date = "2025-10-28"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_daily_stats_file_path(self):
        """Test DailyStats generates correct file path."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)

            expected_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "daily",
                f"{self.test_date}_current.json"
            )
            self.assertEqual(daily_stats.file_path, expected_path)

    def test_daily_stats_save_and_load(self):
        """Test DailyStats can save and load data."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create and save daily stats
            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats.load()

            test_word_stats = create_empty_word_stats()
            test_word_stats["exposed"] = True
            daily_stats.set_word_stats("test_word", test_word_stats)
            self.assertTrue(daily_stats.save())

            # Load in new instance
            daily_stats2 = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats2.load()

            loaded_word_stats = daily_stats2.get_word_stats("test_word")
            self.assertTrue(loaded_word_stats["exposed"])

    def test_daily_stats_exists(self):
        """Test DailyStats.exists class method."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Should not exist initially
            self.assertFalse(DailyStats.exists(self.test_user_id, self.test_date, "current", self.test_language))

            # Create and save
            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats.load()
            daily_stats.save()

            # Should exist now
            self.assertTrue(DailyStats.exists(self.test_user_id, self.test_date, "current", self.test_language))

    def test_daily_stats_get_available_dates(self):
        """Test DailyStats.get_available_dates returns correct dates."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create multiple daily stats
            dates = ["2025-10-26", "2025-10-27", "2025-10-28"]
            for date in dates:
                daily_stats = DailyStats(self.test_user_id, date, "current", self.test_language)
                daily_stats.load()
                daily_stats.save()

            # Get available dates
            available_dates = DailyStats.get_available_dates(self.test_user_id, "current", self.test_language)

            # Verify all dates are returned in sorted order
            self.assertEqual(available_dates, dates)

    def test_daily_stats_compress_to_gzip(self):
        """Test DailyStats can compress to gzip."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create and save daily stats
            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats.load()
            daily_stats.set_word_stats("test_word", create_empty_word_stats())
            daily_stats.save()

            # Compress to gzip
            result = daily_stats.compress_to_gzip()
            self.assertTrue(result)

            # Verify gzip file exists and regular file is removed
            self.assertTrue(os.path.exists(daily_stats.gzip_file_path))
            self.assertFalse(os.path.exists(daily_stats.file_path))

    def test_daily_stats_load_from_gzip(self):
        """Test DailyStats can load from gzip."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create, save, and compress daily stats
            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats.load()
            test_stats = create_empty_word_stats()
            test_stats["exposed"] = True
            daily_stats.set_word_stats("test_word", test_stats)
            daily_stats.save()
            daily_stats.compress_to_gzip()

            # Load in new instance
            daily_stats2 = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats2.load()

            # Verify data was loaded from gzip
            self.assertTrue(daily_stats2.is_gzip_loaded)
            loaded_word_stats = daily_stats2.get_word_stats("test_word")
            self.assertTrue(loaded_word_stats["exposed"])

    def test_daily_stats_cannot_save_gzip_loaded(self):
        """Test DailyStats cannot save if loaded from gzip."""
        with patch('web.blueprints.trakaido.userstats.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create, save, and compress
            daily_stats = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats.load()
            daily_stats.set_word_stats("test_word", create_empty_word_stats())
            daily_stats.save()
            daily_stats.compress_to_gzip()

            # Load from gzip
            daily_stats2 = DailyStats(self.test_user_id, self.test_date, "current", self.test_language)
            daily_stats2.load()

            # Try to save (should fail)
            result = daily_stats2.save()
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
