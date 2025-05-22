import unittest
import tempfile
import os
import json
from pathlib import Path
import tomli_w

from common.config.user_config import (
    UserConfigManager,
    AdminRole,
    init_user_config_manager,
    get_user_config_manager
)

class UserConfigTestBase(unittest.TestCase):
    """Base class for user config tests with shared setup."""
    
    @classmethod
    def setUpClass(cls):
        """Create temporary config file for all tests."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.config_path = os.path.join(cls.temp_dir, "test_admin.toml")
        
        # Sample valid configuration
        cls.valid_config = {
            "admins": {
                "super_admin": [
                    "super@example.com",
                    "admin1@example.com"
                ],
                "channel_admin": [
                    "channel@example.com",
                    "admin2@example.com"
                ]
            }
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

class TestUserConfigManager(UserConfigTestBase):
    """Test UserConfigManager configuration loading and validation."""
    
    def test_load_valid_admin_configuration(self):
        """Test loading a valid admin configuration file."""
        manager = UserConfigManager(self.config_path)
        self.assertEqual(len(manager.admin_users), 4)
        self.assertEqual(manager.admin_users["super@example.com"], AdminRole.SUPER_ADMIN)
        self.assertEqual(manager.admin_users["channel@example.com"], AdminRole.CHANNEL_ADMIN)
    
    def test_check_admin_status_correctly(self):
        """Test is_admin method correctly identifies admin users."""
        manager = UserConfigManager(self.config_path)
        
        # Admin users
        self.assertTrue(manager.is_admin("super@example.com"))
        self.assertTrue(manager.is_admin("channel@example.com"))
        
        # Non-admin users
        self.assertFalse(manager.is_admin("regular@example.com"))
        self.assertFalse(manager.is_admin(""))
    
    def test_get_admin_role_correctly(self):
        """Test get_admin_role method returns correct roles."""
        manager = UserConfigManager(self.config_path)
        
        # Check roles
        self.assertEqual(manager.get_admin_role("super@example.com"), AdminRole.SUPER_ADMIN)
        self.assertEqual(manager.get_admin_role("channel@example.com"), AdminRole.CHANNEL_ADMIN)
        
        # Non-admin user
        self.assertIsNone(manager.get_admin_role("regular@example.com"))
    
    def test_check_super_admin_status(self):
        """Test is_super_admin method correctly identifies super admins."""
        manager = UserConfigManager(self.config_path)
        
        # Super admin
        self.assertTrue(manager.is_super_admin("super@example.com"))
        self.assertTrue(manager.is_super_admin("admin1@example.com"))
        
        # Channel admin (not super admin)
        self.assertFalse(manager.is_super_admin("channel@example.com"))
        
        # Non-admin user
        self.assertFalse(manager.is_super_admin("regular@example.com"))
    
    def test_check_channel_admin_access(self):
        """Test has_channel_admin_access method."""
        manager = UserConfigManager(self.config_path)
        
        # Create mock user objects with admin_channel_access
        class MockUser:
            def __init__(self, admin_channel_access=None):
                self.admin_channel_access = admin_channel_access
        
        # User with access to specific channels
        user_with_access = MockUser(json.dumps(["channel1", "channel2"]))
        self.assertTrue(manager.has_channel_admin_access(user_with_access, "channel1"))
        self.assertTrue(manager.has_channel_admin_access(user_with_access, "channel2"))
        self.assertFalse(manager.has_channel_admin_access(user_with_access, "channel3"))
        
        # User with no access
        user_no_access = MockUser(json.dumps([]))
        self.assertFalse(manager.has_channel_admin_access(user_no_access, "channel1"))
        
        # User with no admin_channel_access field
        user_none = MockUser(None)
        self.assertFalse(manager.has_channel_admin_access(user_none, "channel1"))
        
        # None user
        self.assertFalse(manager.has_channel_admin_access(None, "channel1"))
    
    def test_handle_invalid_admin_role(self):
        """Test handling of invalid admin role in config."""
        invalid_config = {
            "admins": {
                "super_admin": ["valid@example.com"],
                "invalid_role": ["invalid@example.com"]
            }
        }
        
        # Create temp file for invalid config
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as f:
            tomli_w.dump(invalid_config, f)
            invalid_path = f.name
            
        try:
            # Should not raise exception but log error and skip invalid role
            manager = UserConfigManager(invalid_path)
            self.assertEqual(len(manager.admin_users), 1)
            self.assertTrue(manager.is_admin("valid@example.com"))
            self.assertFalse(manager.is_admin("invalid@example.com"))
        finally:
            os.unlink(invalid_path)
    
    def test_handle_missing_config_file(self):
        """Test handling of missing config file."""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent.toml")
        
        # Should not raise exception but initialize with empty admin_users
        manager = UserConfigManager(nonexistent_path)
        self.assertEqual(len(manager.admin_users), 0)
    
    def test_handle_invalid_json_in_channel_access(self):
        """Test handling of invalid JSON in channel_access field."""
        manager = UserConfigManager(self.config_path)
        
        # Create mock user objects with invalid JSON
        class MockUser:
            def __init__(self, admin_channel_access=None):
                self.admin_channel_access = admin_channel_access
        
        # User with invalid JSON
        user_invalid_json = MockUser("not valid json")
        self.assertFalse(manager.has_channel_admin_access(user_invalid_json, "channel1"))
        
        # User with non-string JSON (TypeError case)
        user_non_string = MockUser(123)
        self.assertFalse(manager.has_channel_admin_access(user_non_string, "channel1"))

class TestUserConfigManagerSingleton(UserConfigTestBase):
    """Test global user config manager instance handling."""
    
    def test_init_and_get(self):
        """Test initialization and retrieval of global instance."""
        # Clear any existing instance
        import common.config.user_config
        common.config.user_config._user_config_manager = None
        
        # Initialize with config
        manager1 = init_user_config_manager(self.config_path)
        self.assertIsNotNone(manager1)
        
        # Get should return same instance
        manager2 = get_user_config_manager()
        self.assertIs(manager1, manager2)
        
        # Test default initialization
        common.config.user_config._user_config_manager = None
        manager3 = get_user_config_manager()
        self.assertIsNotNone(manager3)

if __name__ == '__main__':
    unittest.main()