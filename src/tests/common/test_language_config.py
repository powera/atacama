"""Tests for the language_config module functionality."""

import unittest
import tempfile
import os
from pathlib import Path
import tomli_w
from unittest.mock import patch

from common.config.language_config import (
    LanguageConfig,
    LanguageManager,
    init_language_manager,
    get_language_manager,
)


class TestLanguageConfig(unittest.TestCase):
    """Test suite for LanguageConfig class."""

    def test_language_config_initialization(self):
        """Test basic initialization of LanguageConfig."""
        lang = LanguageConfig(
            name="Lithuanian", code="lt", subdomains=["lt"], audio_dir_name="lithuanian"
        )

        self.assertEqual(lang.name, "Lithuanian")
        self.assertEqual(lang.code, "lt")
        self.assertEqual(lang.subdomains, ["lt"])
        self.assertEqual(lang.audio_dir_name, "lithuanian")
        self.assertEqual(lang.character_set, "")  # Default value

    def test_language_config_with_character_set(self):
        """Test initialization with character set."""
        lang = LanguageConfig(
            name="Lithuanian",
            code="lt",
            subdomains=["lt"],
            audio_dir_name="lithuanian",
            character_set="aąbcčdeęėfghiįyjklmnoprsštuųūvzž",
        )

        self.assertEqual(lang.character_set, "aąbcčdeęėfghiįyjklmnoprsštuųūvzž")

    def test_language_config_multiple_subdomains(self):
        """Test initialization with multiple subdomains."""
        lang = LanguageConfig(
            name="Chinese", code="zh", subdomains=["zh", "cn"], audio_dir_name="chinese"
        )

        self.assertEqual(lang.subdomains, ["zh", "cn"])


class LanguageManagerTestBase(unittest.TestCase):
    """Base class for language manager tests with shared setup."""

    @classmethod
    def setUpClass(cls):
        """Create temporary config file for all tests."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_languages.toml")

        # Sample valid configuration
        cls.valid_config = {
            "languages": {
                "lithuanian": {
                    "name": "Lithuanian",
                    "code": "lt",
                    "subdomains": ["lt"],
                    "audio_dir_name": "lithuanian",
                    "character_set": "aąbcčdeęėfghiįyjklmnoprsštuųūvzž",
                },
                "chinese": {
                    "name": "Chinese",
                    "code": "zh",
                    "subdomains": ["zh", "cn"],
                    "audio_dir_name": "chinese",
                    "character_set": "",
                },
                "french": {
                    "name": "French",
                    "code": "fr",
                    "subdomains": ["fr"],
                    "audio_dir_name": "french",
                    "character_set": "aàâäbcçdeéèêëfghiîïjklmnoôöpqrstuùûüvwxyz",
                },
            },
            "defaults": {"default_language": "lithuanian"},
        }

        # Write valid config
        with open(cls.config_path, "wb") as f:
            tomli_w.dump(cls.valid_config, f)

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary files."""
        try:
            os.unlink(cls.config_path)
            os.rmdir(cls.temp_dir)
        except Exception:
            pass


class TestLanguageManager(LanguageManagerTestBase):
    """Test LanguageManager configuration loading and validation."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        manager = LanguageManager(self.config_path)

        # Check languages loaded correctly
        self.assertEqual(len(manager.languages), 3)
        self.assertIn("lithuanian", manager.languages)
        self.assertIn("chinese", manager.languages)
        self.assertIn("french", manager.languages)

        # Check subdomain mapping
        self.assertEqual(manager.subdomain_to_language["lt"], "lithuanian")
        self.assertEqual(manager.subdomain_to_language["zh"], "chinese")
        self.assertEqual(manager.subdomain_to_language["cn"], "chinese")
        self.assertEqual(manager.subdomain_to_language["fr"], "french")

    def test_get_language_from_host_direct_match(self):
        """Test get_language_from_host with direct subdomain match."""
        manager = LanguageManager(self.config_path)

        self.assertEqual(manager.get_language_from_host("lt.trakaido.com"), "lithuanian")
        self.assertEqual(manager.get_language_from_host("zh.trakaido.com"), "chinese")
        self.assertEqual(manager.get_language_from_host("cn.trakaido.com"), "chinese")
        self.assertEqual(manager.get_language_from_host("fr.trakaido.com"), "french")

    def test_get_language_from_host_with_port(self):
        """Test get_language_from_host with hostname containing port."""
        manager = LanguageManager(self.config_path)

        self.assertEqual(manager.get_language_from_host("lt.trakaido.com:8080"), "lithuanian")
        self.assertEqual(manager.get_language_from_host("zh.example.com:443"), "chinese")

    def test_get_language_from_host_staging_subdomain(self):
        """Test get_language_from_host with staging subdomain."""
        manager = LanguageManager(self.config_path)

        # Staging subdomains should map to the same language as their base
        self.assertEqual(manager.get_language_from_host("lt-staging.trakaido.com"), "lithuanian")
        self.assertEqual(manager.get_language_from_host("zh-staging.trakaido.com"), "chinese")
        self.assertEqual(manager.get_language_from_host("fr-staging.trakaido.com"), "french")

        # Staging with port
        self.assertEqual(
            manager.get_language_from_host("lt-staging.trakaido.com:8080"), "lithuanian"
        )

    def test_get_language_from_host_staging_not_for_unknown(self):
        """Test that staging suffix doesn't match unknown base subdomains."""
        manager = LanguageManager(self.config_path)

        # Unknown-staging should fall back to default, not match anything
        self.assertEqual(
            manager.get_language_from_host("unknown-staging.trakaido.com"), "lithuanian"
        )

    def test_get_language_from_host_default_fallback(self):
        """Test get_language_from_host falls back to default language."""
        manager = LanguageManager(self.config_path)

        # Unknown subdomain falls back to default
        self.assertEqual(manager.get_language_from_host("unknown.trakaido.com"), "lithuanian")
        self.assertEqual(manager.get_language_from_host("www.trakaido.com"), "lithuanian")

    def test_get_language_from_host_no_subdomain(self):
        """Test get_language_from_host with no subdomain."""
        manager = LanguageManager(self.config_path)

        # No subdomain falls back to default
        self.assertEqual(manager.get_language_from_host("trakaido.com"), "lithuanian")
        self.assertEqual(manager.get_language_from_host("localhost"), "lithuanian")

    def test_get_language_config(self):
        """Test get_language_config returns correct configuration."""
        manager = LanguageManager(self.config_path)

        # Get existing language
        lang_config = manager.get_language_config("chinese")
        self.assertEqual(lang_config.name, "Chinese")
        self.assertEqual(lang_config.code, "zh")
        self.assertEqual(lang_config.subdomains, ["zh", "cn"])

        # Get non-existent language (falls back to default)
        lang_config = manager.get_language_config("nonexistent")
        self.assertEqual(lang_config.name, "Lithuanian")

    def test_get_all_language_keys(self):
        """Test get_all_language_keys returns all configured languages."""
        manager = LanguageManager(self.config_path)

        keys = manager.get_all_language_keys()
        self.assertEqual(set(keys), {"lithuanian", "chinese", "french"})

    def test_validate_config_no_languages(self):
        """Test validation fails when no languages are defined."""
        invalid_config = {"languages": {}, "defaults": {"default_language": "lithuanian"}}

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name

        try:
            with self.assertRaises(ValueError) as context:
                LanguageManager(invalid_path)
            self.assertIn("No languages defined", str(context.exception))
        finally:
            os.unlink(invalid_path)

    def test_validate_config_missing_default_language(self):
        """Test validation fails when default language is not in language list."""
        invalid_config = {
            "languages": {
                "chinese": {
                    "name": "Chinese",
                    "code": "zh",
                    "subdomains": ["zh"],
                    "audio_dir_name": "chinese",
                }
            },
            "defaults": {"default_language": "lithuanian"},  # Not in languages list
        }

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name

        try:
            with self.assertRaises(ValueError) as context:
                LanguageManager(invalid_path)
            self.assertIn("Default language 'lithuanian' not found", str(context.exception))
        finally:
            os.unlink(invalid_path)

    def test_duplicate_subdomain(self):
        """Test validation fails when duplicate subdomains are found."""
        invalid_config = {
            "languages": {
                "language1": {
                    "name": "Language 1",
                    "code": "l1",
                    "subdomains": ["duplicate"],
                    "audio_dir_name": "lang1",
                },
                "language2": {
                    "name": "Language 2",
                    "code": "l2",
                    "subdomains": ["duplicate"],  # Duplicate subdomain
                    "audio_dir_name": "lang2",
                },
            },
            "defaults": {"default_language": "language1"},
        }

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name

        try:
            with self.assertRaises(ValueError) as context:
                LanguageManager(invalid_path)
            self.assertIn("Duplicate subdomain", str(context.exception))
        finally:
            os.unlink(invalid_path)


class TestLanguageManagerSingleton(LanguageManagerTestBase):
    """Test global language manager instance handling."""

    def test_init_language_manager(self):
        """Test initialization of global language manager instance."""
        # Clear any existing instance
        import common.config.language_config

        common.config.language_config._language_manager = None

        # Initialize with config
        manager1 = init_language_manager(self.config_path)
        self.assertIsNotNone(manager1)

        # Should return the same instance
        manager2 = get_language_manager()
        self.assertIs(manager1, manager2)

    def test_get_language_manager_auto_init(self):
        """Test get_language_manager auto-initializes if needed."""
        # Clear any existing instance
        import common.config.language_config

        common.config.language_config._language_manager = None

        # Mock DEFAULT_CONFIG_PATH to use our test config
        with patch("common.config.language_config.DEFAULT_CONFIG_PATH", Path(self.config_path)):
            # Should auto-initialize
            manager = get_language_manager()
            self.assertIsNotNone(manager)
            self.assertIsInstance(manager, LanguageManager)

            # Second call should return same instance
            manager2 = get_language_manager()
            self.assertIs(manager, manager2)


if __name__ == "__main__":
    unittest.main()
