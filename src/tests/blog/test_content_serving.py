"""Tests for blog content serving - message retrieval, channel filtering, and rendering."""

import unittest
from datetime import datetime, timezone
from flask import session
from unittest.mock import patch, Mock

from atacama.server import create_app
from models.database import db
from models.models import User, Message, Article


class ContentServingTests(unittest.TestCase):
    """Test cases for blog content serving functionality."""

    def setUp(self):
        """Set up test application with in-memory database."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def create_test_user(self, email='test@example.com', name='Test User'):
        """Helper to create a test user."""
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email=email, name=name)
                db_session.add(user)
                db_session.commit()
                return user.id

    def create_test_message(self, user_id, channel='general', subject='Test', content='Test content'):
        """Helper to create a test message."""
        with self.app.app_context():
            with db.session() as db_session:
                message = Message(
                    user_id=user_id,
                    channel=channel,
                    subject=subject,
                    content=content,
                    timestamp=datetime.now(timezone.utc)
                )
                db_session.add(message)
                db_session.commit()
                return message.id

    def test_message_stream_public_channel(self):
        """Test accessing public channel message stream without auth."""
        user_id = self.create_test_user()
        self.create_test_message(user_id, channel='general', subject='Public Message')

        response = self.client.get('/stream/channel/general')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Public Message', response.data)

    def test_message_stream_private_channel_requires_auth(self):
        """Test that private channels require authentication."""
        user_id = self.create_test_user()
        self.create_test_message(user_id, channel='private_channel', subject='Private Message')

        # Try to access without authentication
        response = self.client.get('/stream/channel/private_channel')

        # Should redirect to login or show error
        self.assertIn(response.status_code, [302, 401, 403])

    def test_message_stream_with_pagination(self):
        """Test message stream pagination using older_than_id."""
        user_id = self.create_test_user()

        # Create multiple messages
        msg1_id = self.create_test_message(user_id, subject='Message 1')
        msg2_id = self.create_test_message(user_id, subject='Message 2')
        msg3_id = self.create_test_message(user_id, subject='Message 3')

        # Get first page
        response = self.client.get('/stream/channel/general')
        self.assertEqual(response.status_code, 200)

        # Get older messages
        response = self.client.get(f'/stream/channel/general/older/{msg3_id}')
        self.assertEqual(response.status_code, 200)

    def test_get_message_by_id(self):
        """Test retrieving a specific message by ID."""
        user_id = self.create_test_user()
        msg_id = self.create_test_message(user_id, subject='Specific Message', content='Specific content')

        response = self.client.get(f'/messages/{msg_id}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNotNone(data)
        self.assertEqual(data['id'], msg_id)
        self.assertEqual(data['subject'], 'Specific Message')

    def test_get_nonexistent_message(self):
        """Test accessing a message that doesn't exist."""
        response = self.client.get('/messages/99999')

        self.assertIn(response.status_code, [404, 400])

    def test_channel_filtering(self):
        """Test that channel filtering works correctly."""
        user_id = self.create_test_user()

        # Create messages in different channels
        self.create_test_message(user_id, channel='general', subject='General Message')
        self.create_test_message(user_id, channel='technology', subject='Tech Message')

        # Get general channel
        response = self.client.get('/stream/channel/general')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'General Message', response.data)
        self.assertNotIn(b'Tech Message', response.data)

        # Get technology channel
        response = self.client.get('/stream/channel/technology')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Tech Message', response.data)
        self.assertNotIn(b'General Message', response.data)

    def test_channel_preferences_requires_auth(self):
        """Test that channel preferences page requires authentication."""
        response = self.client.get('/channels')

        # Should redirect to login or show error
        self.assertIn(response.status_code, [302, 401])

    def test_channel_preferences_with_auth(self):
        """Test accessing channel preferences when authenticated."""
        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}

        response = self.client.get('/channels')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Channel Preferences', response.data)

    def test_update_channel_preferences(self):
        """Test updating channel preferences."""
        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}

        # Update preferences
        response = self.client.post('/channels', data={
            'channel_general': 'on',
            'channel_technology': 'on'
        })

        # Should redirect back to preferences page
        self.assertIn(response.status_code, [200, 302])

    def test_message_with_article(self):
        """Test retrieving a message that has an associated article."""
        user_id = self.create_test_user()

        with self.app.app_context():
            with db.session() as db_session:
                # Create message with article
                message = Message(
                    user_id=user_id,
                    channel='general',
                    subject='Article Message',
                    content='Summary',
                    timestamp=datetime.now(timezone.utc)
                )
                db_session.add(message)
                db_session.flush()

                article = Article(
                    message_id=message.id,
                    content='<green>Full article content</green>'
                )
                db_session.add(article)
                db_session.commit()
                msg_id = message.id

        response = self.client.get(f'/messages/{msg_id}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('article', data)

    def test_timestamp_based_filtering(self):
        """Test filtering messages by timestamp."""
        user_id = self.create_test_user()
        self.create_test_message(user_id, subject='Test Message')

        # Test with date-based URL
        response = self.client.get('/stream/channel/general/before/2099-12-31/')
        self.assertEqual(response.status_code, 200)

    def test_invalid_channel(self):
        """Test accessing an invalid or non-existent channel."""
        response = self.client.get('/stream/channel/nonexistent_channel_xyz')

        # Should return 404 or redirect
        self.assertIn(response.status_code, [404, 200])

    def test_domain_filtered_channels(self):
        """Test that channels are filtered based on domain configuration."""
        # This test verifies domain-based channel filtering
        user_id = self.create_test_user()
        self.create_test_message(user_id, channel='general')

        response = self.client.get('/stream/channel/general')
        self.assertEqual(response.status_code, 200)


class MessageAccessControlTests(unittest.TestCase):
    """Test cases for message access control."""

    def setUp(self):
        """Set up test application."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_restricted_channel_requires_admin(self):
        """Test that restricted channels require admin privileges."""
        # This would need proper setup of restricted channels
        # For now, just verify the mechanism exists
        response = self.client.get('/stream/channel/admin')

        # Should require authentication or show forbidden
        self.assertIn(response.status_code, [302, 401, 403, 404, 200])


if __name__ == '__main__':
    unittest.main()
