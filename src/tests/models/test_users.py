"""Tests for the users module functionality."""

import unittest
from unittest.mock import patch, MagicMock, ANY
import json
from datetime import datetime

from models.users import (
    is_user_admin,
    get_or_create_user,
    get_user_by_id,
    get_user_email_domain,
    check_admin_approval,
    check_channel_access,
    get_user_allowed_channels,
    grant_channel_access_by_id,
    revoke_channel_access_by_id,
    get_user_channel_access_by_id,
    get_all_users
)
from models.models import User, MessageType
from common.config.channel_config import ChannelConfig, AccessLevel
import constants

class TestUsers(unittest.TestCase):
    """Test suite for users module."""
    
    def setUp(self):
        """Set up test fixtures."""
        constants.init_testing()
        
        # Create a test user
        self.user = User(
            id=1,
            email="test@example.com",
            name="Test User",
            channel_preferences=json.dumps({
                "private": True,
                "public": True
            }),
            admin_channel_access=json.dumps({
                "restricted": "2024-01-15T14:30:00Z"
            })
        )
        
        # Create a mock session
        self.mock_session = MagicMock()
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = self.user
        
    def test_is_user_admin(self):
        """Test checking if a user is an admin."""
        with patch('models.users.get_user_config_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.is_admin.return_value = True
            mock_get_manager.return_value = mock_manager
            
            # Test admin user
            self.assertTrue(is_user_admin("admin@example.com"))
            mock_manager.is_admin.assert_called_with("admin@example.com")
            
            # Test non-admin user
            mock_manager.is_admin.return_value = False
            self.assertFalse(is_user_admin("user@example.com"))
            mock_manager.is_admin.assert_called_with("user@example.com")
    
    def test_get_or_create_user_existing(self):
        """Test retrieving an existing user."""
        request_user = {
            "email": "test@example.com",
            "name": "Test User"
        }
        
        # Test with existing user
        result = get_or_create_user(self.mock_session, request_user)
        self.assertEqual(result, self.user)
        self.mock_session.add.assert_not_called()
    
    def test_get_or_create_user_new(self):
        """Test creating a new user."""
        # Set up mock to return None (user doesn't exist)
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        request_user = {
            "email": "new@example.com",
            "name": "New User"
        }
        
        # Test with new user
        result = get_or_create_user(self.mock_session, request_user)
        
        # Verify a new user was created with correct attributes
        self.mock_session.add.assert_called_once()
        self.mock_session.flush.assert_called_once()
        self.assertEqual(result.email, "new@example.com")
        self.assertEqual(result.name, "New User")
    
    def test_get_user_by_id(self):
        """Test retrieving a user by ID."""
        with patch('sqlalchemy.orm.Session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = self.user
            mock_execute.return_value = mock_result
            
            # Test with existing user
            result = get_user_by_id(self.mock_session, 1)
            self.assertEqual(result, self.user)
            
            # Test with non-existent user
            mock_result.scalar_one_or_none.return_value = None
            result = get_user_by_id(self.mock_session, 999)
            self.assertIsNone(result)
    
    def test_get_user_email_domain(self):
        """Test extracting domain from user email."""
        # Test with valid user
        self.assertEqual(get_user_email_domain(self.user), "example.com")
        
        # Test with None user
        self.assertIsNone(get_user_email_domain(None))
        
        # Test with user having no email
        user_no_email = User(id=2, name="No Email")
        self.assertIsNone(get_user_email_domain(user_no_email))
    
    @patch('models.users.db.session')
    def test_check_admin_approval(self, mock_session):
        """Test checking admin channel access."""
        mock_session.return_value.__enter__.return_value.query.return_value.get.return_value = self.user
        
        # Test with approved channel
        self.assertTrue(check_admin_approval(1, "restricted"))
        
        # Test with non-approved channel
        self.assertFalse(check_admin_approval(1, "other_channel"))
        
        # Test with non-existent user
        mock_session.return_value.__enter__.return_value.query.return_value.get.return_value = None
        self.assertFalse(check_admin_approval(999, "restricted"))
    
    @patch('models.users.get_channel_manager')
    def test_check_channel_access(self, mock_get_manager):
        """Test checking channel access permissions."""
        mock_manager = MagicMock()
        mock_channel_config = ChannelConfig(
            name="private",
            description="Private Channel",
            access_level=AccessLevel.PRIVATE
        )
        mock_manager.get_channel_config.return_value = mock_channel_config
        mock_manager.check_system_access.return_value = True
        mock_get_manager.return_value = mock_manager
        
        # Test with valid channel and user
        with patch('models.users.check_admin_approval') as mock_check_admin:
            mock_check_admin.return_value = False
            self.assertTrue(check_channel_access("private", self.user))
            
            # Test with admin-approved channel
            mock_check_admin.return_value = True
            self.assertTrue(check_channel_access("restricted", self.user))
            
            # Test with preferences ignored
            self.assertTrue(check_channel_access("private", self.user, ignore_preferences=True))
            
            # Test with system access denied
            mock_manager.check_system_access.return_value = False
            self.assertFalse(check_channel_access("private", self.user))
            
            # Test with invalid channel
            mock_manager.get_channel_config.return_value = None
            self.assertFalse(check_channel_access("invalid", self.user))
            
            # Test with None channel (should default to "private")
            mock_manager.get_channel_config.return_value = mock_channel_config
            mock_manager.check_system_access.return_value = True
            self.assertTrue(check_channel_access(None, self.user))
            
            # Test with invalid preferences JSON
            user_with_bad_prefs = User(
                id=3,
                email="bad@example.com",
                name="Bad Prefs",
                channel_preferences="invalid-json"
            )
            self.assertTrue(check_channel_access("private", user_with_bad_prefs))
    
    @patch('models.users.get_channel_manager')
    def test_get_user_allowed_channels(self, mock_get_manager):
        """Test getting list of allowed channels."""
        mock_manager = MagicMock()
        mock_manager.get_channel_names.return_value = ["private", "public", "restricted"]
        mock_get_manager.return_value = mock_manager
        
        # Mock check_channel_access to respect user preferences
        with patch('models.users.check_channel_access') as mock_check_access:
            def check_access_side_effect(channel, user, ignore_preferences=False):
                if channel == "private" or channel == "public":
                    return True
                return False
            
            mock_check_access.side_effect = check_access_side_effect
            
            # Test with user
            allowed = get_user_allowed_channels(self.user)
            self.assertEqual(set(allowed), {"private", "public"})
            
            # Test with ignore_preferences
            def check_access_all(channel, user, ignore_preferences=False):
                return True
            
            mock_check_access.side_effect = check_access_all
            allowed = get_user_allowed_channels(self.user, ignore_preferences=True)
            self.assertEqual(set(allowed), {"private", "public", "restricted"})
    
    def test_grant_channel_access_by_id(self):
        """Test granting channel access to a user."""
        # Mock channel manager
        with patch('models.users.get_channel_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_channel_config = MagicMock()
            mock_channel_config.requires_admin = True
            mock_manager.get_channel_config.return_value = mock_channel_config
            mock_get_manager.return_value = mock_manager
            
            # Mock get_user_by_id
            with patch('models.users.get_user_by_id') as mock_get_user:
                mock_get_user.return_value = self.user
                
                # Test granting access
                result = grant_channel_access_by_id(self.mock_session, 1, "new_channel")
                self.assertTrue(result)
                
                # Verify the user's admin_channel_access was updated
                access = json.loads(self.user.admin_channel_access)
                self.assertIn("new_channel", access)
                
                # Test with non-admin channel
                mock_channel_config.requires_admin = False
                result = grant_channel_access_by_id(self.mock_session, 1, "public")
                self.assertFalse(result)
                
                # Test with non-existent channel
                mock_manager.get_channel_config.return_value = None
                result = grant_channel_access_by_id(self.mock_session, 1, "invalid")
                self.assertFalse(result)
                
                # Test with non-existent user
                mock_get_user.return_value = None
                mock_manager.get_channel_config.return_value = mock_channel_config
                mock_channel_config.requires_admin = True
                result = grant_channel_access_by_id(self.mock_session, 999, "new_channel")
                self.assertFalse(result)
    
    def test_revoke_channel_access_by_id(self):
        """Test revoking channel access from a user."""
        # Mock channel manager
        with patch('models.users.get_channel_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_channel_config = MagicMock()
            mock_channel_config.requires_admin = True
            mock_manager.get_channel_config.return_value = mock_channel_config
            mock_get_manager.return_value = mock_manager
            
            # Mock get_user_by_id
            with patch('models.users.get_user_by_id') as mock_get_user:
                mock_get_user.return_value = self.user
                
                # Test revoking access
                result = revoke_channel_access_by_id(self.mock_session, 1, "restricted")
                self.assertTrue(result)
                
                # Verify the user's admin_channel_access was updated
                access = json.loads(self.user.admin_channel_access)
                self.assertNotIn("restricted", access)
                
                # Test with non-admin channel
                mock_channel_config.requires_admin = False
                result = revoke_channel_access_by_id(self.mock_session, 1, "public")
                self.assertFalse(result)
                
                # Test with non-existent channel
                mock_manager.get_channel_config.return_value = None
                result = revoke_channel_access_by_id(self.mock_session, 1, "invalid")
                self.assertFalse(result)
                
                # Test with non-existent user
                mock_get_user.return_value = None
                mock_manager.get_channel_config.return_value = mock_channel_config
                mock_channel_config.requires_admin = True
                result = revoke_channel_access_by_id(self.mock_session, 999, "restricted")
                self.assertFalse(result)
    
    def test_get_user_channel_access_by_id(self):
        """Test getting a user's channel access."""
        # Mock get_user_by_id
        with patch('models.users.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = self.user
            
            # Test getting access for existing user
            access = get_user_channel_access_by_id(self.mock_session, 1)
            self.assertEqual(access, {"restricted": "2024-01-15T14:30:00Z"})
            
            # Test with non-existent user
            mock_get_user.return_value = None
            access = get_user_channel_access_by_id(self.mock_session, 999)
            self.assertEqual(access, {})
    
    def test_get_all_users(self):
        """Test getting all users."""
        with patch('sqlalchemy.orm.Session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [self.user]
            mock_execute.return_value = mock_result
            
            # Test getting all users
            users = get_all_users(self.mock_session)
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0], self.user)


if __name__ == '__main__':
    unittest.main()