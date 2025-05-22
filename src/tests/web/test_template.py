import unittest
from datetime import datetime
from flask import url_for
from flask.testing import FlaskClient
from typing import Dict, Any

from models.database import db
from models.models import Email, User, Base
from web.server import create_app

class TemplateTests(unittest.TestCase):
    def setUp(self):
        """Set up test application with in-memory database."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })
        self.client = self.app.test_client()
        
            
    def tearDown(self):
        """Clean up after tests by dropping all tables."""
        db.cleanup()

    def create_test_user(self) -> Dict[str, Any]:
        """Helper to create a test user and return user data."""
        with self.app.app_context():
            with db.session() as session:
                user = User(
                    email="test@example.com",
                    name="Test User"
                )
                session.add(user)
                session.commit()
                return {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name
                }

    def create_test_message(self, **kwargs) -> tuple[int, dict]:
        """
        Helper to create a test message.
        
        :return: Tuple of (message_id, message_data)
        """
        defaults = {
            'subject': 'Test Subject',
            'content': 'Test content',
            'processed_content': '<p>Test content</p>',
            'created_at': datetime.utcnow(),
            'channel': 'private'
        }
        defaults.update(kwargs)
        
        if 'author' in kwargs and isinstance(kwargs['author'], dict):
            # If author is passed as a dict, get the User object
            with db.session() as session:
                author = session.query(User).get(kwargs['author']['id'])
                defaults['author'] = author
        
        with self.app.app_context():
            with db.session() as session:
                message = Email(**defaults)
                session.add(message)
                session.commit()
                # Return id and basic data while still in session
                return message.id, {
                    'subject': message.subject,
                    'content': message.content,
                    'processed_content': message.processed_content
                }

    def login(self, user_data: Dict[str, Any]) -> None:
        """Helper to simulate user login."""
        with self.client.session_transaction() as session:
            session['user'] = {
                'email': user_data['email'],
                'name': user_data['name']
            }

    def test_message_template_authenticated(self):
        """Test the message.html template renders correctly for authenticated users."""
        with self.app.app_context():
            # Create test data
            user_data = self.create_test_user()
            message_id, message_data = self.create_test_message(author=user_data)
            
            # Login the user
            self.login(user_data)
            
            # Generate URL for message view
            url = url_for('content.get_message', message_id=message_id)
            
            # Test authenticated view
            response = self.client.get(url,
                                       headers={'Accept': 'text/html'})
            self.assertEqual(response.status_code, 200)
            
            # Verify content elements
            content = response.get_data(as_text=True)
            self.assertIn(message_data['subject'], content)
            self.assertIn(message_data['processed_content'], content)
            self.assertIn(user_data['name'], content)

    def test_stream_template(self):
        """Test the stream.html template renders correctly."""
        with self.app.app_context():
            # Create test messages
            user_data = self.create_test_user()
            messages = []
            for i in range(3):
                message_id, data = self.create_test_message(
                    subject=f'Test Message {i}',
                    author=user_data,
                    channel="sports",  # message needs a channel in default
                )
                messages.append((message_id, data))
            
            # Test stream view
            response = self.client.get(url_for('content.message_stream'),
                                       headers={'Accept': 'text/html'})
            self.assertEqual(response.status_code, 200)
            
            # Check for message elements
            content = response.get_data(as_text=True)
            for _, data in messages:
                self.assertIn(data['subject'], content)

    def test_login_template(self):
        """Test the login.html template renders correctly."""
        with self.app.app_context():
            response = self.client.get(url_for('auth.login'),
                                       headers={'Accept': 'text/html'})
            self.assertEqual(response.status_code, 200)
            
            # Check for essential login page elements
            content = response.get_data(as_text=True)
            self.assertIn('Login', content)
            self.assertIn('https://accounts.google.com/gsi/client', content)

    def test_error_template(self):
        """Test error.html template renders correctly."""
        with self.app.app_context():
            # Test 404 error page - specify we want HTML response
            response = self.client.get('/nonexistent-page', 
                                     headers={'Accept': 'text/html'})
            self.assertEqual(response.status_code, 404)
            
            content = response.get_data(as_text=True)
            self.assertIn('Page Not Found', content)
            self.assertIn('404', content)

if __name__ == '__main__':
    unittest.main()
