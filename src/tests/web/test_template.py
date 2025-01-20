import unittest
from datetime import datetime
from flask import url_for
from flask.testing import FlaskClient
from typing import Dict, Any

from common.database import db
from common.models import Email, User
from web.server import create_app

class TemplateTests(unittest.TestCase):
    def setUp(self):
        """Set up test application with in-memory database."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'  # Use in-memory database
        })
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.initialize(test=True)  # This will create tables in the test database
            
    def tearDown(self):
        """Clean up after tests."""
        with self.app.app_context():
            db.initialize(test=True)  # Reset database between tests

    def create_test_user(self) -> User:
        """Helper to create a test user."""
        with self.app.app_context():
            with db.session() as session:
                user = User(
                    email="test@example.com",
                    name="Test User"
                )
                session.add(user)
                session.commit()
                return user

    def create_test_message(self, **kwargs) -> Email:
        """Helper to create a test message."""
        defaults = {
            'subject': 'Test Subject',
            'content': 'Test content',
            'processed_content': '<p>Test content</p>',
            'created_at': datetime.utcnow(),
            'channel': 'private'
        }
        defaults.update(kwargs)
        
        with self.app.app_context():
            with db.session() as session:
                message = Email(**defaults)
                session.add(message)
                session.commit()
                return message

    def test_message_template(self):
        """Test the message.html template renders correctly."""
        with self.app.app_context():
            # Create test data
            user = self.create_test_user()
            message = self.create_test_message(author=user)
            
            # Generate URL for message view
            url = url_for('content.view_message', message_id=message.id)
            
            # Test unauthenticated view
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            
            # Verify basic content elements
            self.assertIn(message.subject, response.get_data(as_text=True))
            self.assertIn(message.processed_content, response.get_data(as_text=True))
            self.assertIn(user.name, response.get_data(as_text=True))

    def test_stream_template(self):
        """Test the stream.html template renders correctly."""
        with self.app.app_context():
            # Create test messages
            user = self.create_test_user()
            for i in range(3):
                self.create_test_message(
                    subject=f'Test Message {i}',
                    author=user
                )
            
            # Test stream view
            response = self.client.get(url_for('content.stream'))
            self.assertEqual(response.status_code, 200)
            
            # Check for message elements
            content = response.get_data(as_text=True)
            self.assertIn('Test Message 0', content)
            self.assertIn('Test Message 1', content)
            self.assertIn('Test Message 2', content)

    def test_login_template(self):
        """Test the login.html template renders correctly."""
        with self.app.app_context():
            response = self.client.get(url_for('auth.login'))
            self.assertEqual(response.status_code, 200)
            
            # Check for essential login page elements
            content = response.get_data(as_text=True)
            self.assertIn('Sign in', content)
            self.assertIn('google-signin', content)

    def test_error_template(self):
        """Test error.html template renders correctly."""
        with self.app.app_context():
            # Test 404 error page
            response = self.client.get('/nonexistent-page')
            self.assertEqual(response.status_code, 404)
            
            content = response.get_data(as_text=True)
            self.assertIn('Page Not Found', content)
            self.assertIn('404', content)

if __name__ == '__main__':
    unittest.main()
