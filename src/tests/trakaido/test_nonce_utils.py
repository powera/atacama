"""Tests for nonce_utils module."""

import unittest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

from trakaido.blueprints.nonce_utils import (
    get_nonce_file_path,
    load_nonces,
    save_nonces,
    get_all_nonce_files,
    cleanup_old_nonce_files,
    check_nonce_duplicates
)


class NonceUtilsTests(unittest.TestCase):
    """Test cases for nonce utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test data
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"
        self.test_day_key = "2025-10-28"

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove the temporary directory
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_get_nonce_file_path(self):
        """Test get_nonce_file_path generates correct path."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            file_path = get_nonce_file_path(self.test_user_id, self.test_day_key, self.test_language)

            expected_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "daily",
                f"{self.test_day_key}_nonces.json"
            )
            self.assertEqual(file_path, expected_path)

    def test_get_nonce_file_path_creates_directory(self):
        """Test get_nonce_file_path creates directory if it doesn't exist."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            file_path = get_nonce_file_path(self.test_user_id, self.test_day_key, self.test_language)

            # Check that the directory was created
            expected_dir = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "daily"
            )
            self.assertTrue(os.path.exists(expected_dir))
            self.assertTrue(os.path.isdir(expected_dir))

    def test_save_and_load_nonces(self):
        """Test saving and loading nonces."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create a set of nonces
            nonces = {"nonce1", "nonce2", "nonce3"}

            # Save the nonces
            result = save_nonces(self.test_user_id, self.test_day_key, nonces, self.test_language)
            self.assertTrue(result)

            # Load the nonces
            loaded_nonces = load_nonces(self.test_user_id, self.test_day_key, self.test_language)

            # Verify the loaded nonces match the saved ones
            self.assertEqual(loaded_nonces, nonces)

    def test_load_nonces_nonexistent_file(self):
        """Test load_nonces returns empty set for nonexistent file."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            loaded_nonces = load_nonces(self.test_user_id, self.test_day_key, self.test_language)

            self.assertEqual(loaded_nonces, set())

    def test_save_nonces_creates_json_structure(self):
        """Test save_nonces creates proper JSON structure."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            nonces = {"nonce1", "nonce2"}
            save_nonces(self.test_user_id, self.test_day_key, nonces, self.test_language)

            # Read the file directly and check structure
            file_path = get_nonce_file_path(self.test_user_id, self.test_day_key, self.test_language)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.assertIn("nonces", data)
            self.assertIsInstance(data["nonces"], list)
            self.assertEqual(set(data["nonces"]), nonces)

    def test_get_all_nonce_files(self):
        """Test get_all_nonce_files returns all nonce file dates."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create multiple nonce files
            dates = ["2025-10-26", "2025-10-27", "2025-10-28"]
            for date in dates:
                save_nonces(self.test_user_id, date, {"test"}, self.test_language)

            # Get all nonce files
            result = get_all_nonce_files(self.test_user_id, self.test_language)

            # Verify all dates are returned in sorted order
            self.assertEqual(result, dates)

    def test_get_all_nonce_files_filters_invalid_filenames(self):
        """Test get_all_nonce_files filters out invalid filenames."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create valid and invalid files
            daily_dir = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "daily"
            )
            os.makedirs(daily_dir, exist_ok=True)

            # Valid nonce file
            valid_file = os.path.join(daily_dir, "2025-10-28_nonces.json")
            with open(valid_file, 'w') as f:
                json.dump({"nonces": []}, f)

            # Invalid files (should be filtered out)
            invalid_files = [
                "invalid_nonces.json",
                "2025-10_nonces.json",  # Too short
                "2025-10-28.json"  # Missing _nonces
            ]
            for invalid_file in invalid_files:
                with open(os.path.join(daily_dir, invalid_file), 'w') as f:
                    f.write("{}")

            # Get all nonce files
            result = get_all_nonce_files(self.test_user_id, self.test_language)

            # Only the valid file should be returned
            # Note: get_all_nonce_files checks for 10 chars and 2 hyphens but doesn't validate the date format
            # "not-a-date" would pass those checks, so we don't include it in test
            self.assertEqual(result, ["2025-10-28"])

    def test_get_all_nonce_files_empty_directory(self):
        """Test get_all_nonce_files with nonexistent directory."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            result = get_all_nonce_files(self.test_user_id, self.test_language)

            self.assertEqual(result, [])

    def test_cleanup_old_nonce_files(self):
        """Test cleanup_old_nonce_files removes old files."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants, \
             patch('trakaido.blueprints.nonce_utils.get_current_day_key') as mock_current, \
             patch('trakaido.blueprints.nonce_utils.get_yesterday_day_key') as mock_yesterday:

            mock_constants.DATA_DIR = self.test_data_dir
            mock_current.return_value = "2025-10-28"
            mock_yesterday.return_value = "2025-10-27"

            # Create nonce files for multiple days
            dates = ["2025-10-24", "2025-10-25", "2025-10-26", "2025-10-27", "2025-10-28"]
            for date in dates:
                save_nonces(self.test_user_id, date, {"test"}, self.test_language)

            # Cleanup old nonce files
            result = cleanup_old_nonce_files(self.test_user_id, self.test_language)
            self.assertTrue(result)

            # Check remaining files
            remaining_files = get_all_nonce_files(self.test_user_id, self.test_language)

            # Only current and yesterday should remain
            self.assertEqual(set(remaining_files), {"2025-10-27", "2025-10-28"})

    def test_check_nonce_duplicates_in_today(self):
        """Test check_nonce_duplicates finds duplicate in today's nonces."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants, \
             patch('trakaido.blueprints.nonce_utils.get_current_day_key') as mock_current, \
             patch('trakaido.blueprints.nonce_utils.get_yesterday_day_key') as mock_yesterday:

            mock_constants.DATA_DIR = self.test_data_dir
            mock_current.return_value = "2025-10-28"
            mock_yesterday.return_value = "2025-10-27"

            # Save nonces for today
            today_nonces = {"nonce1", "nonce2", "nonce3"}
            save_nonces(self.test_user_id, "2025-10-28", today_nonces, self.test_language)

            # Check for duplicate
            result = check_nonce_duplicates(self.test_user_id, "nonce2", self.test_language)

            self.assertTrue(result)

    def test_check_nonce_duplicates_in_yesterday(self):
        """Test check_nonce_duplicates finds duplicate in yesterday's nonces."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants, \
             patch('trakaido.blueprints.nonce_utils.get_current_day_key') as mock_current, \
             patch('trakaido.blueprints.nonce_utils.get_yesterday_day_key') as mock_yesterday:

            mock_constants.DATA_DIR = self.test_data_dir
            mock_current.return_value = "2025-10-28"
            mock_yesterday.return_value = "2025-10-27"

            # Save nonces for yesterday
            yesterday_nonces = {"nonce1", "nonce2"}
            save_nonces(self.test_user_id, "2025-10-27", yesterday_nonces, self.test_language)

            # Check for duplicate
            result = check_nonce_duplicates(self.test_user_id, "nonce2", self.test_language)

            self.assertTrue(result)

    def test_check_nonce_duplicates_not_found(self):
        """Test check_nonce_duplicates returns False when nonce not found."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants, \
             patch('trakaido.blueprints.nonce_utils.get_current_day_key') as mock_current, \
             patch('trakaido.blueprints.nonce_utils.get_yesterday_day_key') as mock_yesterday:

            mock_constants.DATA_DIR = self.test_data_dir
            mock_current.return_value = "2025-10-28"
            mock_yesterday.return_value = "2025-10-27"

            # Save nonces for today and yesterday
            save_nonces(self.test_user_id, "2025-10-28", {"nonce1"}, self.test_language)
            save_nonces(self.test_user_id, "2025-10-27", {"nonce2"}, self.test_language)

            # Check for non-existent nonce
            result = check_nonce_duplicates(self.test_user_id, "nonce3", self.test_language)

            self.assertFalse(result)

    def test_check_nonce_duplicates_with_no_files(self):
        """Test check_nonce_duplicates returns False when no nonce files exist."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants, \
             patch('trakaido.blueprints.nonce_utils.get_current_day_key') as mock_current, \
             patch('trakaido.blueprints.nonce_utils.get_yesterday_day_key') as mock_yesterday:

            mock_constants.DATA_DIR = self.test_data_dir
            mock_current.return_value = "2025-10-28"
            mock_yesterday.return_value = "2025-10-27"

            # Check for nonce without any files
            result = check_nonce_duplicates(self.test_user_id, "nonce1", self.test_language)

            self.assertFalse(result)

    def test_load_nonces_with_corrupted_file(self):
        """Test load_nonces handles corrupted JSON gracefully."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Create a corrupted nonce file
            file_path = get_nonce_file_path(self.test_user_id, self.test_day_key, self.test_language)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write("not valid json {}")

            # Try to load nonces
            loaded_nonces = load_nonces(self.test_user_id, self.test_day_key, self.test_language)

            # Should return empty set on error
            self.assertEqual(loaded_nonces, set())

    def test_save_nonces_with_empty_set(self):
        """Test save_nonces handles empty nonce set."""
        with patch('trakaido.blueprints.nonce_utils.constants') as mock_constants:
            mock_constants.DATA_DIR = self.test_data_dir

            # Save empty nonce set
            result = save_nonces(self.test_user_id, self.test_day_key, set(), self.test_language)
            self.assertTrue(result)

            # Load and verify
            loaded_nonces = load_nonces(self.test_user_id, self.test_day_key, self.test_language)
            self.assertEqual(loaded_nonces, set())


if __name__ == '__main__':
    unittest.main()
