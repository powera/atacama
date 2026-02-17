import unittest
import tempfile
import os
import copy
from pathlib import Path
import tomli
import tomli_w

from common.config.channel_config import (
    ChannelManager,
    ChannelConfig,
    AccessLevel,
    init_channel_manager,
    get_channel_manager,
)


class ChannelConfigTestBase(unittest.TestCase):
    """Base class for channel config tests with shared setup."""

    @classmethod
    def setUpClass(cls):
        """Create temporary config file for all tests."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_channels.toml")

        # Sample valid configuration
        cls.valid_config = {
            "channels": {
                "public": {"description": "Public channel", "access_level": "public"},
                "private": {"description": "Private channel", "access_level": "private"},
                "restricted": {
                    "description": "Restricted channel",
                    "access_level": "restricted",
                    "domain_restriction": "example.com",
                    "requires_admin": True,
                },
            },
            "defaults": {
                "default_channel": "private",
                "default_preferences": ["public", "private"],
            },
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


class TestChannelConfig(ChannelConfigTestBase):
    """Test ChannelConfig dataclass and methods."""

    def test_public_channel(self):
        """Test public channel configuration."""
        config = ChannelConfig(
            name="public", description="Public channel", access_level=AccessLevel.PUBLIC
        )
        self.assertFalse(config.requires_auth)
        self.assertTrue(config.is_public)

    def test_private_channel(self):
        """Test private channel configuration."""
        config = ChannelConfig(
            name="private", description="Private channel", access_level=AccessLevel.PRIVATE
        )
        self.assertTrue(config.requires_auth)
        self.assertFalse(config.is_public)

    def test_restricted_channel(self):
        """Test restricted channel with domain."""
        config = ChannelConfig(
            name="restricted",
            description="Domain restricted channel",
            access_level=AccessLevel.RESTRICTED,
            domain_restriction="example.com",
        )
        self.assertTrue(config.requires_auth)
        self.assertFalse(config.is_public)

    def test_get_display_name_with_custom_name(self):
        """Test get_display_name method with custom display name."""
        config = ChannelConfig(
            name="test_channel",
            description="Test channel",
            access_level=AccessLevel.PUBLIC,
            display_name="Custom Display Name",
        )
        self.assertEqual(config.get_display_name(), "Custom Display Name")

    def test_get_display_name_without_custom_name(self):
        """Test get_display_name method without custom display name."""
        config = ChannelConfig(
            name="test_channel", description="Test channel", access_level=AccessLevel.PUBLIC
        )
        self.assertEqual(config.get_display_name(), "Test_Channel")

    def test_default_group_value(self):
        """Test default group value is set correctly."""
        config = ChannelConfig(
            name="test_channel", description="Test channel", access_level=AccessLevel.PUBLIC
        )
        self.assertEqual(config.group, "General")

    def test_custom_group_value(self):
        """Test custom group value is set correctly."""
        config = ChannelConfig(
            name="test_channel",
            description="Test channel",
            access_level=AccessLevel.PUBLIC,
            group="Custom Group",
        )
        self.assertEqual(config.group, "Custom Group")

    def test_requires_admin_default(self):
        """Test requires_admin default value."""
        config = ChannelConfig(
            name="test_channel", description="Test channel", access_level=AccessLevel.RESTRICTED
        )
        self.assertFalse(config.requires_admin)

    def test_requires_admin_custom(self):
        """Test requires_admin custom value."""
        config = ChannelConfig(
            name="test_channel",
            description="Test channel",
            access_level=AccessLevel.RESTRICTED,
            requires_admin=True,
        )
        self.assertTrue(config.requires_admin)


class TestChannelManager(ChannelConfigTestBase):
    """Test ChannelManager configuration loading and validation."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        manager = ChannelManager(self.config_path)
        self.assertEqual(len(manager.channels), 3)
        self.assertEqual(manager.default_channel, "private")
        self.assertEqual(len(manager.default_preferences), 2)

    def test_invalid_access_level(self):
        """Test error on invalid access level."""
        invalid_config = copy.deepcopy(self.valid_config)
        invalid_config["channels"]["bad"] = {
            "description": "Bad channel",
            "access_level": "invalid",
        }

        # Create temp file for invalid config
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name

        try:
            with self.assertRaises(ValueError):
                ChannelManager(invalid_path)
        finally:
            os.unlink(invalid_path)

    def test_missing_default_channel(self):
        """Test error when default channel doesn't exist."""
        invalid_config = copy.deepcopy(self.valid_config)
        invalid_config["defaults"]["default_channel"] = "nonexistent"

        # Create temp file for invalid config
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name

        try:
            with self.assertRaises(ValueError):
                ChannelManager(invalid_path)
        finally:
            os.unlink(invalid_path)


class TestChannelAccess(ChannelConfigTestBase):
    """Test channel access control logic."""

    def setUp(self):
        """Initialize channel manager with test config."""
        self.manager = ChannelManager(self.config_path)

    def test_public_access(self):
        """Test public channel access."""
        self.assertTrue(self.manager.check_system_access("public"))
        self.assertTrue(self.manager.check_system_access("public", email="user@example.com"))

    def test_private_access(self):
        """Test private channel access requirements."""
        self.assertFalse(self.manager.check_system_access("private"))  # No email
        self.assertTrue(self.manager.check_system_access("private", email="user@example.com"))

    def test_restricted_access(self):
        """Test restricted channel access with domain and admin."""
        # No authentication
        self.assertFalse(self.manager.check_system_access("restricted"))

        # Wrong domain
        self.assertFalse(self.manager.check_system_access("restricted", email="user@wrong.com"))

        # Correct domain but no admin
        self.assertFalse(
            self.manager.check_system_access(
                "restricted", email="user@example.com", has_admin_access=False
            )
        )

        # Correct domain and admin
        self.assertTrue(
            self.manager.check_system_access(
                "restricted", email="user@example.com", has_admin_access=True
            )
        )


class TestChannelManagerSingleton(ChannelConfigTestBase):
    """Test global channel manager instance handling."""

    def test_init_and_get(self):
        """Test initialization and retrieval of global instance."""
        # Clear any existing instance
        import common.config.channel_config

        common.config.channel_config._channel_manager = None

        # Initialize with config
        manager1 = init_channel_manager(self.config_path)
        self.assertIsNotNone(manager1)

        # Get should return same instance
        manager2 = get_channel_manager()
        self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()
