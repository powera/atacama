"""Tests for grammarstats module."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from trakaido.blueprints.grammarstats import (
    GrammarStats,
    validate_concept_id,
    validate_concept_stats,
    MAX_CONCEPT_ID_LENGTH,
)


class GrammarStatsValidationTests(unittest.TestCase):
    """Test cases for concept ID and stats validation."""

    def test_validate_concept_id_valid_simple(self):
        """Test validate_concept_id accepts simple valid IDs."""
        self.assertTrue(validate_concept_id("nominative"))
        self.assertTrue(validate_concept_id("present-tense"))
        self.assertTrue(validate_concept_id("a"))  # Single letter

    def test_validate_concept_id_valid_hyphenated(self):
        """Test validate_concept_id accepts hyphenated IDs."""
        self.assertTrue(validate_concept_id("nominative-form"))
        self.assertTrue(validate_concept_id("past-perfect-tense"))
        self.assertTrue(validate_concept_id("a-b-c"))

    def test_validate_concept_id_invalid_uppercase(self):
        """Test validate_concept_id rejects uppercase letters."""
        self.assertFalse(validate_concept_id("Nominative"))
        self.assertFalse(validate_concept_id("UPPERCASE"))
        self.assertFalse(validate_concept_id("mixedCase"))

    def test_validate_concept_id_invalid_numbers(self):
        """Test validate_concept_id rejects numbers."""
        self.assertFalse(validate_concept_id("lesson1"))
        self.assertFalse(validate_concept_id("123"))
        self.assertFalse(validate_concept_id("verb-2"))

    def test_validate_concept_id_invalid_special_chars(self):
        """Test validate_concept_id rejects special characters."""
        self.assertFalse(validate_concept_id("verb_form"))  # underscore
        self.assertFalse(validate_concept_id("verb.form"))  # dot
        self.assertFalse(validate_concept_id("verb form"))  # space
        self.assertFalse(validate_concept_id("verb@form"))  # special char

    def test_validate_concept_id_invalid_start_end(self):
        """Test validate_concept_id rejects IDs starting/ending with hyphen."""
        self.assertFalse(validate_concept_id("-nominative"))
        self.assertFalse(validate_concept_id("nominative-"))
        self.assertFalse(validate_concept_id("-nominative-"))

    def test_validate_concept_id_invalid_empty(self):
        """Test validate_concept_id rejects empty strings."""
        self.assertFalse(validate_concept_id(""))
        self.assertFalse(validate_concept_id(None))

    def test_validate_concept_id_invalid_too_long(self):
        """Test validate_concept_id rejects strings over max length."""
        long_id = "a" * (MAX_CONCEPT_ID_LENGTH + 1)
        self.assertFalse(validate_concept_id(long_id))

        # But exactly max length should be valid
        exact_id = "a" * MAX_CONCEPT_ID_LENGTH
        self.assertTrue(validate_concept_id(exact_id))

    def test_validate_concept_stats_valid(self):
        """Test validate_concept_stats accepts valid stats."""
        self.assertTrue(validate_concept_stats({"viewCount": 3, "lastViewedAt": 1705000000000}))
        self.assertTrue(validate_concept_stats({"viewCount": 0, "lastViewedAt": None}))

    def test_validate_concept_stats_invalid_view_count(self):
        """Test validate_concept_stats rejects invalid viewCount."""
        self.assertFalse(
            validate_concept_stats({"viewCount": -1, "lastViewedAt": 1705000000000})  # negative
        )
        self.assertFalse(
            validate_concept_stats(
                {"viewCount": "3", "lastViewedAt": 1705000000000}  # string instead of int
            )
        )
        self.assertFalse(
            validate_concept_stats(
                {"viewCount": 3.5, "lastViewedAt": 1705000000000}  # float instead of int
            )
        )

    def test_validate_concept_stats_invalid_last_viewed(self):
        """Test validate_concept_stats rejects invalid lastViewedAt."""
        self.assertFalse(validate_concept_stats({"viewCount": 3, "lastViewedAt": -1}))  # negative
        self.assertFalse(validate_concept_stats({"viewCount": 3, "lastViewedAt": 0}))  # zero
        self.assertFalse(
            validate_concept_stats({"viewCount": 3, "lastViewedAt": "1705000000000"})  # string
        )

    def test_validate_concept_stats_invalid_not_dict(self):
        """Test validate_concept_stats rejects non-dict input."""
        self.assertFalse(validate_concept_stats(None))
        self.assertFalse(validate_concept_stats([]))
        self.assertFalse(validate_concept_stats("stats"))


class GrammarStatsStorageTests(unittest.TestCase):
    """Test cases for GrammarStats storage class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_123"
        self.test_language = "lithuanian"

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_grammar_stats_file_path(self):
        """Test GrammarStats generates correct file path."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)

            expected_path = os.path.join(
                self.test_data_dir,
                "trakaido",
                self.test_user_id,
                self.test_language,
                "grammar_stats.json",
            )
            self.assertEqual(grammar_stats.file_path, expected_path)

    def test_grammar_stats_load_empty(self):
        """Test GrammarStats.load returns empty stats for new users."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            result = grammar_stats.load()

            self.assertTrue(result)
            self.assertEqual(grammar_stats.stats, {"stats": {}})

    def test_grammar_stats_save_and_load(self):
        """Test GrammarStats can save and load data."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            # Create and save grammar stats
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.load()
            grammar_stats.stats = {
                "stats": {"nominative-form": {"viewCount": 3, "lastViewedAt": 1705000000000}}
            }
            self.assertTrue(grammar_stats.save())

            # Load in new instance
            grammar_stats2 = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats2.load()

            self.assertEqual(grammar_stats2.stats["stats"]["nominative-form"]["viewCount"], 3)
            self.assertEqual(
                grammar_stats2.stats["stats"]["nominative-form"]["lastViewedAt"], 1705000000000
            )

    def test_grammar_stats_get_concept_stats(self):
        """Test GrammarStats.get_concept_stats returns correct data."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.stats = {
                "stats": {"nominative-form": {"viewCount": 5, "lastViewedAt": 1705000000000}}
            }

            # Existing concept
            concept_stats = grammar_stats.get_concept_stats("nominative-form")
            self.assertIsNotNone(concept_stats)
            self.assertEqual(concept_stats["viewCount"], 5)

            # Non-existing concept
            self.assertIsNone(grammar_stats.get_concept_stats("nonexistent"))

    def test_grammar_stats_record_view_new_concept(self):
        """Test GrammarStats.record_view creates new concept entry."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.load()

            result = grammar_stats.record_view("present-tense")

            self.assertEqual(result["viewCount"], 1)
            self.assertIsNotNone(result["lastViewedAt"])
            self.assertIsInstance(result["lastViewedAt"], int)
            self.assertGreater(result["lastViewedAt"], 0)

    def test_grammar_stats_record_view_increments(self):
        """Test GrammarStats.record_view increments existing concept."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.load()

            # Record multiple views
            grammar_stats.record_view("nominative-form")
            grammar_stats.record_view("nominative-form")
            result = grammar_stats.record_view("nominative-form")

            self.assertEqual(result["viewCount"], 3)

    def test_grammar_stats_record_view_updates_timestamp(self):
        """Test GrammarStats.record_view updates lastViewedAt."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.stats = {
                "stats": {
                    "nominative-form": {
                        "viewCount": 2,
                        "lastViewedAt": 1000000000000,  # old timestamp
                    }
                }
            }

            result = grammar_stats.record_view("nominative-form")

            self.assertEqual(result["viewCount"], 3)
            self.assertGreater(result["lastViewedAt"], 1000000000000)

    def test_grammar_stats_save_without_load_fails(self):
        """Test GrammarStats.save fails if not loaded."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            # Don't call load()

            result = grammar_stats.save()
            self.assertFalse(result)


class GrammarStatsAPIEndpointsTests(unittest.TestCase):
    """Integration tests for grammar stats API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_data_dir = tempfile.mkdtemp()
        self.test_user_id = "test_user_456"
        self.test_language = "lithuanian"

        # Create a mock user object
        self.mock_user = MagicMock()
        self.mock_user.id = self.test_user_id

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_get_grammar_stats_empty(self):
        """Test GET /api/trakaido/grammarstats/ returns empty stats for new user."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import get_grammar_stats
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context():
                g.user = self.mock_user
                g.current_language = self.test_language

                response = get_grammar_stats()

                # Response is a tuple (json_response, status_code) or just json_response
                if isinstance(response, tuple):
                    data = response[0].get_json()
                else:
                    data = response.get_json()

                self.assertEqual(data, {"stats": {}})

    def test_get_grammar_stats_with_data(self):
        """Test GET /api/trakaido/grammarstats/ returns existing stats."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            # Pre-populate stats
            grammar_stats = GrammarStats(self.test_user_id, self.test_language)
            grammar_stats.stats = {
                "stats": {"nominative-form": {"viewCount": 3, "lastViewedAt": 1705000000000}}
            }
            grammar_stats.save()

            from trakaido.blueprints.grammarstats import get_grammar_stats
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context():
                g.user = self.mock_user
                g.current_language = self.test_language

                response = get_grammar_stats()

                if isinstance(response, tuple):
                    data = response[0].get_json()
                else:
                    data = response.get_json()

                self.assertEqual(data["stats"]["nominative-form"]["viewCount"], 3)

    def test_record_grammar_view_success(self):
        """Test POST /api/trakaido/grammarstats/view records a view."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            with patch(
                "trakaido.blueprints.grammarstats.check_nonce_duplicates", return_value=False
            ):
                with patch("trakaido.blueprints.grammarstats.load_nonces", return_value=set()):
                    with patch("trakaido.blueprints.grammarstats.save_nonces", return_value=True):
                        from trakaido.blueprints.grammarstats import record_grammar_view
                        from flask import Flask, g

                        app = Flask(__name__)
                        with app.test_request_context(
                            json={"conceptId": "nominative-form", "nonce": "test-nonce-123"}
                        ):
                            g.user = self.mock_user
                            g.current_language = self.test_language

                            response = record_grammar_view()

                            if isinstance(response, tuple):
                                data = response[0].get_json()
                                status = response[1]
                            else:
                                data = response.get_json()
                                status = 200

                            self.assertEqual(status, 200)
                            self.assertTrue(data["success"])
                            self.assertEqual(data["stats"]["viewCount"], 1)

    def test_record_grammar_view_duplicate_nonce(self):
        """Test POST /api/trakaido/grammarstats/view returns 409 for duplicate nonce."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            with patch(
                "trakaido.blueprints.grammarstats.check_nonce_duplicates", return_value=True
            ):
                from trakaido.blueprints.grammarstats import record_grammar_view
                from flask import Flask, g

                app = Flask(__name__)
                with app.test_request_context(
                    json={"conceptId": "nominative-form", "nonce": "duplicate-nonce"}
                ):
                    g.user = self.mock_user
                    g.current_language = self.test_language

                    response = record_grammar_view()

                    if isinstance(response, tuple):
                        data = response[0].get_json()
                        status = response[1]
                    else:
                        data = response.get_json()
                        status = 200

                    self.assertEqual(status, 409)
                    self.assertEqual(data["error"], "duplicate_nonce")

    def test_record_grammar_view_invalid_concept_id(self):
        """Test POST /api/trakaido/grammarstats/view returns 400 for invalid concept ID."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import record_grammar_view
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context(json={"conceptId": "INVALID_ID", "nonce": "test-nonce"}):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = record_grammar_view()

                if isinstance(response, tuple):
                    data = response[0].get_json()
                    status = response[1]
                else:
                    data = response.get_json()
                    status = 200

                self.assertEqual(status, 400)
                self.assertIn("Invalid concept ID", data["error"])

    def test_record_grammar_view_missing_fields(self):
        """Test POST /api/trakaido/grammarstats/view returns 400 for missing fields."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import record_grammar_view
            from flask import Flask, g

            app = Flask(__name__)

            # Missing nonce
            with app.test_request_context(json={"conceptId": "nominative-form"}):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = record_grammar_view()
                if isinstance(response, tuple):
                    status = response[1]
                else:
                    status = 200
                self.assertEqual(status, 400)

            # Missing conceptId
            with app.test_request_context(json={"nonce": "test-nonce"}):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = record_grammar_view()
                if isinstance(response, tuple):
                    status = response[1]
                else:
                    status = 200
                self.assertEqual(status, 400)

    def test_replace_grammar_stats_success(self):
        """Test PUT /api/trakaido/grammarstats/ replaces stats."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import replace_grammar_stats
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context(
                json={
                    "stats": {
                        "nominative-form": {"viewCount": 5, "lastViewedAt": 1705000000000},
                        "present-tense": {"viewCount": 2, "lastViewedAt": 1706000000000},
                    }
                }
            ):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = replace_grammar_stats()

                if isinstance(response, tuple):
                    data = response[0].get_json()
                    status = response[1]
                else:
                    data = response.get_json()
                    status = 200

                self.assertEqual(status, 200)
                self.assertTrue(data["success"])

                # Verify stats were saved
                grammar_stats = GrammarStats(self.test_user_id, self.test_language)
                grammar_stats.load()
                self.assertEqual(grammar_stats.stats["stats"]["nominative-form"]["viewCount"], 5)
                self.assertEqual(grammar_stats.stats["stats"]["present-tense"]["viewCount"], 2)

    def test_replace_grammar_stats_invalid_concept_id(self):
        """Test PUT /api/trakaido/grammarstats/ returns 400 for invalid concept ID."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import replace_grammar_stats
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context(
                json={"stats": {"INVALID_ID": {"viewCount": 5, "lastViewedAt": 1705000000000}}}
            ):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = replace_grammar_stats()

                if isinstance(response, tuple):
                    status = response[1]
                else:
                    status = 200

                self.assertEqual(status, 400)

    def test_replace_grammar_stats_invalid_stats(self):
        """Test PUT /api/trakaido/grammarstats/ returns 400 for invalid stats values."""
        with patch("constants.DATA_DIR", self.test_data_dir):
            from trakaido.blueprints.grammarstats import replace_grammar_stats
            from flask import Flask, g

            app = Flask(__name__)
            with app.test_request_context(
                json={
                    "stats": {"nominative-form": {"viewCount": -1, "lastViewedAt": 1705000000000}}
                }
            ):
                g.user = self.mock_user
                g.current_language = self.test_language

                response = replace_grammar_stats()

                if isinstance(response, tuple):
                    status = response[1]
                else:
                    status = 200

                self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
