"""Tests for the messages module functionality."""

import unittest
from flask import Flask
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime
import json

from common.messages import (
    get_user_email_domain,
    check_admin_approval,
    check_channel_access,
    get_user_allowed_channels,
    check_message_access,
    get_message_by_id,
    get_message_chain,
    get_filtered_messages
)
from common.models import User, Email
from common.channel_config import ChannelConfig, AccessLevel
import constants

class TestMessages(unittest.TestCase):
    """Test suite for messages module."""
    
    def setUp(self):
        """Set up test fixtures."""
        constants.init_testing()
        self.app = Flask(__name__)
        self.app_context = self.app.app_context()
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
        
        self.message = Email(
            id=1,
            subject="Test Message",
            content="Test content",
            channel="private",
            author_id=1,
            created_at=datetime.utcnow()
        )

    def test_get_user_email_domain(self):
        """Test extracting domain from user email."""
        self.assertEqual(get_user_email_domain(self.user), "example.com")
        self.assertIsNone(get_user_email_domain(None))
        
        # Test user with no email
        user_no_email = User(id=2, name="No Email")
        self.assertIsNone(get_user_email_domain(user_no_email))

    @patch('common.messages.db.session')
    def test_check_admin_approval(self, mock_session):
        """Test checking admin channel access."""
        mock_session.return_value.__enter__.return_value.query.return_value.get.return_value = self.user
        
        self.assertTrue(check_admin_approval(1, "restricted"))
        self.assertFalse(check_admin_approval(1, "other_channel"))
        
        # Test non-existent user
        mock_session.return_value.__enter__.return_value.query.return_value.get.return_value = None
        self.assertFalse(check_admin_approval(999, "restricted"))
 
    @patch('common.messages.get_channel_manager')
    def test_check_channel_access(self, mock_get_manager):
        """Test checking channel access permissions."""
        mock_manager = MagicMock()
        mock_manager.get_channel_config.return_value = ChannelConfig(
            name="test",
            description="Test Channel",
            access_level=AccessLevel.PRIVATE
        )
        mock_manager.check_system_access.return_value = True
        mock_get_manager.return_value = mock_manager
        
        # Test basic access
        self.assertTrue(check_channel_access("private", self.user))
        
        # Test with preferences ignored
        self.assertTrue(check_channel_access("private", self.user, ignore_preferences=True))
        
        # Test invalid channel
        mock_manager.get_channel_config.return_value = None
        self.assertFalse(check_channel_access("invalid", self.user))

    @patch('common.messages.get_channel_manager')
    def test_get_user_allowed_channels(self, mock_get_manager):
        """Test getting list of allowed channels."""
        mock_manager = MagicMock()
        mock_manager.get_channel_names.return_value = ["private", "public", "restricted"]
        mock_get_manager.return_value = mock_manager
        
        # Mock check_channel_access to respect user preferences
        with patch('common.messages.check_channel_access') as mock_check_access:
            def check_access_side_effect(channel, user, ignore_preferences=False):
                if ignore_preferences:
                    return True
                preferences = json.loads(user.channel_preferences)
                return preferences.get(channel, False)
            
            mock_check_access.side_effect = check_access_side_effect
            
            # Test with preferences
            allowed = get_user_allowed_channels(self.user)
            self.assertEqual(set(allowed), {"private", "public"})
            
            # Test with preferences ignored
            allowed = get_user_allowed_channels(self.user, ignore_preferences=True)
            self.assertEqual(set(allowed), {"private", "public", "restricted"})

    def test_check_message_access(self):
        """Test checking access to specific messages."""
        with self.app_context:
            with patch('common.messages.check_channel_access') as mock_check:
                mock_check.return_value = True
                with patch('common.messages.g') as mock_g:
                    mock_g.user = self.user
                    self.assertTrue(check_message_access(self.message))
                    mock_check.assert_called_with(self.message.channel, self.user, True)

    @patch('common.messages.db.session')
    def test_get_message_by_id(self, mock_session):
        """Test retrieving message by ID."""
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = self.message
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query
        
        with patch('common.messages.check_message_access') as mock_check:
            mock_check.return_value = True
            
            result = get_message_by_id(1)
            self.assertEqual(result, self.message)
            
            # Test non-existent message
            mock_query.options.return_value.filter.return_value.first.return_value = None
            result = get_message_by_id(999)
            self.assertIsNone(result)

    @patch('common.messages.db.session')
    def test_get_message_chain(self, mock_session):
        """Test retrieving full message chain."""
        parent = Email(id=2, channel="private")
        child = Email(id=3, channel="private")
        self.message.parent = parent
        self.message.children = [child]
        
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = self.message
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query
        
        with patch('common.messages.check_message_access') as mock_check:
            mock_check.return_value = True
            
            chain = get_message_chain(1)
            self.assertEqual(len(chain), 3)
            self.assertEqual([m.id for m in chain], [2, 1, 3])

    @patch('common.messages.get_channel_manager')
    def test_get_filtered_messages(self, mock_get_manager):
        """Test retrieving filtered message list."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = [self.message]
        
        # Mock channel manager
        mock_manager = MagicMock()
        mock_manager.get_channel_config.return_value = ChannelConfig(
            name="test",
            description="Test Channel",
            access_level=AccessLevel.PRIVATE
        )
        mock_get_manager.return_value = mock_manager
        
        with self.app_context:
            with patch('common.messages.g') as mock_g:
                mock_g.user = self.user
                
                messages, has_more = get_filtered_messages(
                    mock_session,
                    older_than_id=None,
                    channel="private"
                )
                
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0], self.message)
                self.assertFalse(has_more)

if __name__ == '__main__':
    unittest.main()
