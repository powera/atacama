"""Tests for userconfig_v2 module (new user configuration API)."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask import g

import constants
from models.database import db
from models.models import User
from atacama.server import create_app
from trakaido.blueprints.userconfig_v2 import (
    DEFAULT_CONFIG,
    VALID_COLOR_SCHEMES,
    VALID_PROFICIENCY_LEVELS,
    _apply_updates,
    _deep_copy_config,
    _merge_with_defaults,
    get_userconfig_file_path,
    load_user_config,
    save_user_config,
    validate_config_update,
)


class UserconfigV2FileOperationsTests(unittest.TestCase):
    """Test file I/O operations for user configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = constants.DATA_DIR
        constants.DATA_DIR = self.temp_dir

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        constants.DATA_DIR = self.original_data_dir

    def test_get_userconfig_file_path(self):
        """Test userconfig file path generation."""
        path = get_userconfig_file_path("123", "lithuanian")
        expected = os.path.join(self.temp_dir, "trakaido", "123", "lithuanian", "userconfig.json")
        self.assertEqual(path, expected)

    def test_load_user_config_returns_defaults_when_no_file(self):
        """Test loading config returns defaults when file doesn't exist."""
        config = load_user_config("123", "lithuanian")

        # Should return default config
        self.assertIn("learning", config)
        self.assertIn("audio", config)
        self.assertIn("display", config)
        self.assertIn("metadata", config)

        # Check default values
        self.assertEqual(config["learning"]["currentLevel"], 1)
        self.assertEqual(config["learning"]["userProficiency"], "beginner")
        self.assertTrue(config["audio"]["enabled"])
        self.assertEqual(config["display"]["colorScheme"], "system")

    def test_save_and_load_user_config(self):
        """Test saving and loading user configuration."""
        user_id = "456"
        test_config = {
            "learning": {
                "currentLevel": 5,
                "userProficiency": "intermediate",
                "journeyAutoAdvance": False,
                "showMotivationalBreaks": True,
            },
            "audio": {"enabled": False, "selectedVoice": "ash", "downloadOnWiFiOnly": True},
            "display": {"colorScheme": "dark", "showGrammarInterstitials": False},
            "metadata": {"hasCompletedOnboarding": True},
        }

        # Save config
        success = save_user_config(user_id, test_config, "lithuanian")
        self.assertTrue(success)

        # Load config
        loaded_config = load_user_config(user_id, "lithuanian")

        # Verify values (excluding lastModified which is auto-generated)
        self.assertEqual(loaded_config["learning"]["currentLevel"], 5)
        self.assertEqual(loaded_config["learning"]["userProficiency"], "intermediate")
        self.assertFalse(loaded_config["learning"]["journeyAutoAdvance"])
        self.assertFalse(loaded_config["audio"]["enabled"])
        self.assertEqual(loaded_config["audio"]["selectedVoice"], "ash")
        self.assertEqual(loaded_config["display"]["colorScheme"], "dark")
        self.assertFalse(loaded_config["display"]["showGrammarInterstitials"])
        self.assertTrue(loaded_config["metadata"]["hasCompletedOnboarding"])

        # Check that lastModified was added
        self.assertIsNotNone(loaded_config["metadata"]["lastModified"])

    def test_load_user_config_with_invalid_json(self):
        """Test loading config with invalid JSON returns defaults."""
        user_id = "789"
        config_file = get_userconfig_file_path(user_id, "lithuanian")

        # Create directory
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        # Write invalid JSON
        with open(config_file, "w") as f:
            f.write("{ invalid json }")

        # Should return default config
        config = load_user_config(user_id, "lithuanian")
        self.assertEqual(config["learning"]["currentLevel"], 1)

    def test_merge_with_defaults(self):
        """Test merging partial config with defaults."""
        partial_config = {"learning": {"currentLevel": 10}, "audio": {"enabled": False}}

        merged = _merge_with_defaults(partial_config)

        # Check merged values
        self.assertEqual(merged["learning"]["currentLevel"], 10)
        self.assertFalse(merged["audio"]["enabled"])

        # Check defaults are present
        self.assertEqual(merged["learning"]["userProficiency"], "beginner")
        self.assertEqual(merged["audio"]["selectedVoice"], "random")
        self.assertEqual(merged["display"]["colorScheme"], "system")

    def test_deep_copy_config(self):
        """Test deep copy creates independent copy."""
        original = {"learning": {"currentLevel": 5}}
        copied = _deep_copy_config(original)

        # Modify copy
        copied["learning"]["currentLevel"] = 10

        # Original should be unchanged
        self.assertEqual(original["learning"]["currentLevel"], 5)


class UserconfigV2ValidationTests(unittest.TestCase):
    """Test validation logic for user configuration updates."""

    def test_validate_valid_learning_config(self):
        """Test validation accepts valid learning configuration."""
        updates = {
            "learning": {
                "currentLevel": 5,
                "userProficiency": "intermediate",
                "journeyAutoAdvance": False,
                "showMotivationalBreaks": True,
            }
        }

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(unknown, [])

    def test_validate_invalid_current_level_too_low(self):
        """Test validation rejects currentLevel < 1."""
        updates = {"learning": {"currentLevel": 0}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertEqual(error["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("currentLevel", error["error"]["details"]["field"])

    def test_validate_invalid_current_level_too_high(self):
        """Test validation rejects currentLevel > 20."""
        updates = {"learning": {"currentLevel": 21}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_invalid_proficiency_level(self):
        """Test validation rejects invalid proficiency level."""
        updates = {"learning": {"userProficiency": "expert"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn("allowedValues", error["error"]["details"])

    def test_validate_valid_audio_config(self):
        """Test validation accepts valid audio configuration."""
        updates = {"audio": {"enabled": True, "selectedVoice": "ash", "downloadOnWiFiOnly": False}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_audio_null_voice_converts_to_random(self):
        """Test validation converts null selectedVoice to 'random'."""
        updates = {"audio": {"selectedVoice": None}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertEqual(updates["audio"]["selectedVoice"], "random")

    def test_validate_invalid_color_scheme(self):
        """Test validation rejects invalid color scheme."""
        updates = {"display": {"colorScheme": "rainbow"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_valid_display_config(self):
        """Test validation accepts valid display configuration."""
        updates = {"display": {"colorScheme": "dark", "showGrammarInterstitials": False}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_accepts_has_completed_onboarding_update(self):
        """Test validation accepts hasCompletedOnboarding updates."""
        updates = {"metadata": {"hasCompletedOnboarding": True}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_rejects_last_modified_update(self):
        """Test validation rejects lastModified updates (read-only)."""
        updates = {"metadata": {"lastModified": "2025-01-01T00:00:00Z"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertEqual(error["error"]["code"], "READ_ONLY_FIELD")
        self.assertIn("lastModified", error["error"]["details"]["field"])

    def test_validate_rejects_invalid_has_completed_onboarding_type(self):
        """Test validation rejects non-boolean hasCompletedOnboarding."""
        updates = {"metadata": {"hasCompletedOnboarding": "yes"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertEqual(error["error"]["code"], "VALIDATION_ERROR")

    def test_validate_ignores_unknown_metadata_fields(self):
        """Test validation ignores unknown metadata fields."""
        updates = {"metadata": {"hasCompletedOnboarding": True, "customField": "value"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIn("metadata.customField", unknown)

    def test_validate_invalid_boolean_type(self):
        """Test validation rejects non-boolean for boolean fields."""
        updates = {"learning": {"journeyAutoAdvance": "yes"}}

        is_valid, error, unknown = validate_config_update(updates)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_multiple_sections(self):
        """Test validation accepts updates across multiple sections."""
        updates = {
            "learning": {"currentLevel": 8},
            "audio": {"enabled": False},
            "display": {"colorScheme": "light"},
        }

        is_valid, error, unknown = validate_config_update(updates)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class UserconfigV2UpdateTests(unittest.TestCase):
    """Test configuration update logic."""

    def test_apply_updates_partial_learning(self):
        """Test applying partial updates to learning section."""
        current = _deep_copy_config(DEFAULT_CONFIG)
        updates = {"learning": {"currentLevel": 7}}

        result = _apply_updates(current, updates)

        # Updated field
        self.assertEqual(result["learning"]["currentLevel"], 7)

        # Unchanged fields
        self.assertEqual(result["learning"]["userProficiency"], "beginner")
        self.assertTrue(result["learning"]["journeyAutoAdvance"])

    def test_apply_updates_multiple_sections(self):
        """Test applying updates to multiple sections."""
        current = _deep_copy_config(DEFAULT_CONFIG)
        updates = {
            "learning": {"currentLevel": 3},
            "audio": {"enabled": False},
            "display": {"colorScheme": "dark"},
        }

        result = _apply_updates(current, updates)

        self.assertEqual(result["learning"]["currentLevel"], 3)
        self.assertFalse(result["audio"]["enabled"])
        self.assertEqual(result["display"]["colorScheme"], "dark")

    def test_apply_updates_does_not_modify_original(self):
        """Test that apply_updates doesn't modify the original config."""
        current = _deep_copy_config(DEFAULT_CONFIG)
        original_level = current["learning"]["currentLevel"]

        updates = {"learning": {"currentLevel": 15}}
        result = _apply_updates(current, updates)

        # Original unchanged
        self.assertEqual(current["learning"]["currentLevel"], original_level)
        # Result updated
        self.assertEqual(result["learning"]["currentLevel"], 15)

    def test_apply_updates_metadata_has_completed_onboarding(self):
        """Test applying hasCompletedOnboarding update."""
        current = _deep_copy_config(DEFAULT_CONFIG)
        updates = {"metadata": {"hasCompletedOnboarding": True}}

        result = _apply_updates(current, updates)

        self.assertTrue(result["metadata"]["hasCompletedOnboarding"])
        # lastModified should remain unchanged by _apply_updates
        self.assertIsNone(result["metadata"]["lastModified"])

    def test_apply_updates_filters_unknown_metadata_fields(self):
        """Test that unknown metadata fields are filtered out."""
        current = _deep_copy_config(DEFAULT_CONFIG)
        updates = {"metadata": {"hasCompletedOnboarding": True, "unknownField": "value"}}

        result = _apply_updates(current, updates)

        self.assertTrue(result["metadata"]["hasCompletedOnboarding"])
        self.assertNotIn("unknownField", result["metadata"])


class UserconfigV2APIEndpointsTests(unittest.TestCase):
    """Test API endpoints for user configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = constants.DATA_DIR
        constants.DATA_DIR = self.temp_dir

        # Create test app
        self.app = create_app(testing=True, blueprint_set="TRAKAIDO")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create test user (db automatically initializes on first session use)
        with db.session() as session:
            self.test_user = User(email="test@example.com", name="Test User")
            session.add(self.test_user)
            session.flush()
            self.user_id = self.test_user.id

    def tearDown(self):
        """Clean up test fixtures."""
        db.cleanup()  # Clean up database between tests
        self.app_context.pop()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        constants.DATA_DIR = self.original_data_dir

    def test_get_user_config_returns_defaults(self):
        """Test GET endpoint returns default config for new user."""
        # Set up authenticated session
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        response = self.client.get("/api/trakaido/userconfig/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIn("learning", data)
        self.assertIn("audio", data)
        self.assertIn("display", data)
        self.assertIn("metadata", data)

        self.assertEqual(data["learning"]["currentLevel"], 1)
        self.assertEqual(data["learning"]["userProficiency"], "beginner")

    def test_patch_user_config_updates_single_field(self):
        """Test PATCH endpoint updates single field."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"learning": {"currentLevel": 5}}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["config"]["learning"]["currentLevel"], 5)
        # Other fields unchanged
        self.assertEqual(data["config"]["learning"]["userProficiency"], "beginner")

    def test_patch_user_config_updates_multiple_fields(self):
        """Test PATCH endpoint updates multiple fields."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {
            "learning": {"currentLevel": 10, "userProficiency": "advanced"},
            "audio": {"selectedVoice": "nova"},
        }

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["config"]["learning"]["currentLevel"], 10)
        self.assertEqual(data["config"]["learning"]["userProficiency"], "advanced")
        self.assertEqual(data["config"]["audio"]["selectedVoice"], "nova")

    def test_patch_user_config_rejects_invalid_data(self):
        """Test PATCH endpoint rejects invalid configuration."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"learning": {"currentLevel": 25}}  # Invalid: > 20

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    def test_patch_user_config_rejects_non_json(self):
        """Test PATCH endpoint rejects non-JSON requests."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data="not json", content_type="text/plain"
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "INVALID_REQUEST")

    def test_patch_user_config_persists_changes(self):
        """Test PATCH endpoint persists changes across requests."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        # First update
        updates = {"learning": {"currentLevel": 7}}
        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Get config to verify persistence
        response = self.client.get("/api/trakaido/userconfig/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertEqual(data["learning"]["currentLevel"], 7)

    def test_patch_user_config_updates_last_modified(self):
        """Test PATCH endpoint updates lastModified timestamp."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"audio": {"enabled": False}}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIsNotNone(data["config"]["metadata"]["lastModified"])
        # Verify it's a valid ISO 8601 timestamp
        from datetime import datetime

        timestamp = data["config"]["metadata"]["lastModified"]
        # Should parse without error
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_get_user_config_with_language_parameter(self):
        """Test GET endpoint accepts language parameter."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        # Save config for specific language
        config = _deep_copy_config(DEFAULT_CONFIG)
        config["learning"]["currentLevel"] = 12
        save_user_config(str(self.user_id), config, "chinese")

        response = self.client.get("/api/trakaido/userconfig/?language=chinese")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertEqual(data["learning"]["currentLevel"], 12)

    def test_patch_user_config_with_language_parameter(self):
        """Test PATCH endpoint accepts language parameter."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"learning": {"currentLevel": 8}}

        response = self.client.patch(
            "/api/trakaido/userconfig/?language=french",
            data=json.dumps(updates),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Verify it was saved for the correct language
        loaded = load_user_config(str(self.user_id), "french")
        self.assertEqual(loaded["learning"]["currentLevel"], 8)

    def test_patch_user_config_ignores_unknown_fields(self):
        """Test PATCH endpoint ignores unknown fields and returns warning."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {
            "learning": {"currentLevel": 5, "experimentalFeature": True},  # Unknown field
            "audio": {"enabled": False, "unknownSetting": "value"},  # Unknown field
            "unknownSection": {"field": "value"},  # Unknown section
        }

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should have warning
        self.assertIn("warning", data)
        self.assertEqual(data["warning"]["code"], "UNKNOWN_FIELDS_IGNORED")
        self.assertIn("ignoredFields", data["warning"])

        # Check that all unknown fields are listed
        ignored = data["warning"]["ignoredFields"]
        self.assertIn("learning.experimentalFeature", ignored)
        self.assertIn("audio.unknownSetting", ignored)
        self.assertIn("unknownSection", ignored)

        # Known fields should be applied
        self.assertEqual(data["config"]["learning"]["currentLevel"], 5)
        self.assertFalse(data["config"]["audio"]["enabled"])

        # Unknown fields should NOT be in config
        self.assertNotIn("experimentalFeature", data["config"]["learning"])
        self.assertNotIn("unknownSetting", data["config"]["audio"])
        self.assertNotIn("unknownSection", data["config"])

    def test_patch_user_config_no_warning_for_valid_fields(self):
        """Test PATCH endpoint does not include warning when all fields are valid."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"learning": {"currentLevel": 3}, "audio": {"enabled": True}}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Should NOT have warning for valid fields
        self.assertNotIn("warning", data)

    def test_patch_user_config_allows_onboarding_completion(self):
        """Test PATCH endpoint allows marking onboarding as completed."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        # Initially should be False
        response = self.client.get("/api/trakaido/userconfig/")
        data = json.loads(response.data)
        self.assertFalse(data["metadata"]["hasCompletedOnboarding"])

        # Mark onboarding as completed
        updates = {"metadata": {"hasCompletedOnboarding": True}}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["metadata"]["hasCompletedOnboarding"])

        # Verify persistence
        response = self.client.get("/api/trakaido/userconfig/")
        data = json.loads(response.data)
        self.assertTrue(data["metadata"]["hasCompletedOnboarding"])

    def test_patch_user_config_rejects_last_modified_update(self):
        """Test PATCH endpoint rejects attempts to set lastModified."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        updates = {"metadata": {"lastModified": "2025-01-01T00:00:00Z"}}

        response = self.client.patch(
            "/api/trakaido/userconfig/", data=json.dumps(updates), content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "READ_ONLY_FIELD")


if __name__ == "__main__":
    unittest.main()
