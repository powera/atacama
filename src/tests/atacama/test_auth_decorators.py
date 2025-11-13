"""Tests for auth decorators in web/decorators/auth.py."""

import unittest
import os
from unittest.mock import patch, MagicMock
from flask import Flask, g, session, request, render_template

from atacama.decorators.auth import _populate_user, require_auth, optional_auth, require_admin
from models.models import User

class AuthDecoratorsTests(unittest.TestCase):
    """Test cases for auth decorators."""
    
    def setUp(self):
        """Set up test application."""
        self.app = Flask(__name__)
        self.app.config.update({
            'TESTING': True,
            'SECRET_KEY': 'test_key'
        })
        
        # Create a test route with require_auth decorator
        @self.app.route('/protected')
        @require_auth
        def protected_route():
            return 'Protected Content'
            
        # Create a test route with optional_auth decorator
        @self.app.route('/optional')
        @optional_auth
        def optional_route():
            return f'Optional Content for {"authenticated" if g.user else "anonymous"} user'
            
        # Create a test route with require_admin decorator
        @self.app.route('/admin')
        @require_admin
        def admin_route():
            return 'Admin Content'
        
    def tearDown(self):
        """Clean up after tests."""
        # Clear Flask globals only if we're in an application context
        with self.app.app_context():
            if hasattr(g, 'user'):
                delattr(g, 'user')
    
    def test_populate_user_with_user_in_session(self):
        """Test _populate_user when user is in session."""
        # Mock user data
        mock_user = User(id=1, email="test@example.com", name="Test User")
        
        # Mock the database session and get_or_create_user function
        with patch('web.decorators.auth.db.session') as mock_db_session, \
             patch('web.decorators.auth.get_or_create_user', return_value=mock_user) as mock_get_user:
            
            # Create a mock session context manager
            mock_session_instance = MagicMock()
            mock_db_session.return_value.__enter__.return_value = mock_session_instance
            
            # Set up the Flask context with a user in session
            with self.app.app_context():
                with self.app.test_request_context():
                    session['user'] = {'email': 'test@example.com', 'name': 'Test User'}
                    
                    # Call the function under test
                    _populate_user()
                    
                    # Verify that g.user was set correctly
                    self.assertEqual(g.user, mock_user)
                    
                    # Verify that get_or_create_user was called with correct arguments
                    mock_get_user.assert_called_once_with(mock_session_instance, session['user'])
                    
                    # Verify that expire_on_commit was set to False
                    self.assertFalse(mock_session_instance.expire_on_commit)
    
    def test_populate_user_with_no_user_in_session(self):
        """Test _populate_user when user is not in session."""
        # Set up the Flask context without a user in session
        with self.app.app_context():
            with self.app.test_request_context():
                # Call the function under test
                _populate_user()
                
                # Verify that g.user was set to None
                self.assertIsNone(g.user)
    
    def test_require_auth_with_authenticated_user(self):
        """Test require_auth decorator with an authenticated user."""
        # Mock user data
        mock_user = User(id=1, email="test@example.com", name="Test User")
        
        # Mock the database session and get_or_create_user function
        with patch('web.decorators.auth.db.session') as mock_db_session, \
             patch('web.decorators.auth.get_or_create_user', return_value=mock_user):
            
            # Create a mock session context manager
            mock_session_instance = MagicMock()
            mock_db_session.return_value.__enter__.return_value = mock_session_instance
            
            # Create a test client
            client = self.app.test_client()
            
            # Set up a session with a user
            with client.session_transaction() as sess:
                sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}
            
            # Access the protected route
            response = client.get('/protected')
            
            # Verify that the route was accessible
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode('utf-8'), 'Protected Content')
    
    def test_require_auth_with_unauthenticated_user(self):
        """Test require_auth decorator with an unauthenticated user."""
        # Mock the render_template function
        with patch('web.decorators.auth.render_template') as mock_render:
            mock_render.return_value = 'Login Page'
            
            # Create a test client
            client = self.app.test_client()
            
            # Access the protected route without a user in session
            response = client.get('/protected')
            
            # Verify that render_template was called with login.html
            mock_render.assert_called_once()
            self.assertEqual(mock_render.call_args[0][0], 'login.html')
            
            # Verify that the response contains the login page
            self.assertEqual(response.data.decode('utf-8'), 'Login Page')
    
    def test_optional_auth_with_authenticated_user(self):
        """Test optional_auth decorator with an authenticated user."""
        # Mock user data
        mock_user = User(id=1, email="test@example.com", name="Test User")
        
        # Mock the database session and get_or_create_user function
        with patch('web.decorators.auth.db.session') as mock_db_session, \
             patch('web.decorators.auth.get_or_create_user', return_value=mock_user):
            
            # Create a mock session context manager
            mock_session_instance = MagicMock()
            mock_db_session.return_value.__enter__.return_value = mock_session_instance
            
            # Create a test client
            client = self.app.test_client()
            
            # Set up a session with a user
            with client.session_transaction() as sess:
                sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}
            
            # Access the optional route
            response = client.get('/optional')
            
            # Verify that the route was accessible and shows authenticated content
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode('utf-8'), 'Optional Content for authenticated user')
    
    def test_optional_auth_with_unauthenticated_user(self):
        """Test optional_auth decorator with an unauthenticated user."""
        # Create a test client
        client = self.app.test_client()
        
        # Access the optional route without a user in session
        response = client.get('/optional')
        
        # Verify that the route was accessible and shows anonymous content
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), 'Optional Content for anonymous user')

    def test_require_auth_sets_auth_required_attribute(self):
        """Test that require_auth sets the __auth_required__ attribute on the decorated function."""
        # Define a function
        def test_func():
            return "Test Function"
        
        # Apply the decorator
        decorated_func = require_auth(test_func)
        
        # Check that the __auth_required__ attribute is set
        self.assertTrue(hasattr(decorated_func, '__auth_required__'))
        self.assertTrue(decorated_func.__auth_required__)
    
    def test_require_auth_preserves_function_metadata(self):
        """Test that require_auth preserves the function's metadata."""
        # Define a function with docstring and name
        def test_func():
            """Test function docstring."""
            return "Test Function"
        
        # Apply the decorator
        decorated_func = require_auth(test_func)
        
        # Check that the function's metadata is preserved
        self.assertEqual(decorated_func.__name__, 'test_func')
        self.assertEqual(decorated_func.__doc__, 'Test function docstring.')
    
    def test_populate_user_with_user_already_in_g(self):
        """Test _populate_user when g.user is already set."""
        # Create a mock user
        mock_user = User(id=1, email="test@example.com", name="Test User")
        
        # Set up the Flask context with g.user already set
        with self.app.app_context():
            with self.app.test_request_context():
                g.user = mock_user
                
                # Call the function under test
                _populate_user()
                
                # Verify that g.user was not changed
                self.assertEqual(g.user, mock_user)

    def test_require_admin_with_admin_user(self):
        """Test require_admin decorator with an admin user."""
        # Mock user data
        mock_user = User(id=1, email="admin@example.com", name="Admin User")
        
        # Mock the database session, get_or_create_user, and user_config_manager
        with patch('web.decorators.auth.db.session') as mock_db_session, \
             patch('web.decorators.auth.get_or_create_user', return_value=mock_user), \
             patch('web.decorators.auth.get_user_config_manager') as mock_config_manager:
            
            # Set up the mock user config manager to return True for is_admin
            mock_manager = MagicMock()
            mock_manager.is_admin.return_value = True
            mock_config_manager.return_value = mock_manager
            
            # Create a mock session context manager
            mock_session_instance = MagicMock()
            mock_db_session.return_value.__enter__.return_value = mock_session_instance
            
            # Create a test client
            client = self.app.test_client()
            
            # Set up a session with a user
            with client.session_transaction() as sess:
                sess['user'] = {'email': 'admin@example.com', 'name': 'Admin User'}
            
            # Access the admin route
            response = client.get('/admin')
            
            # Verify that the route was accessible
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode('utf-8'), 'Admin Content')
            
            # Verify that is_admin was called with the correct email
            mock_manager.is_admin.assert_called_once_with(mock_user.email)
    
    def test_require_admin_with_non_admin_user(self):
        """Test require_admin decorator with a non-admin user."""
        # Mock user data
        mock_user = User(id=1, email="user@example.com", name="Regular User")
        
        # Mock the database session, get_or_create_user, and user_config_manager
        with patch('web.decorators.auth.db.session') as mock_db_session, \
             patch('web.decorators.auth.get_or_create_user', return_value=mock_user), \
             patch('web.decorators.auth.get_user_config_manager') as mock_config_manager, \
             patch('web.decorators.auth.render_template') as mock_render:
            
            # Set up the mock user config manager to return False for is_admin
            mock_manager = MagicMock()
            mock_manager.is_admin.return_value = False
            mock_config_manager.return_value = mock_manager
            
            # Set up mock render_template to return a 403 error page
            # Flask expects a tuple with (response, status_code) or a Response object
            mock_render.return_value = 'Forbidden'
            
            # Create a mock session context manager
            mock_session_instance = MagicMock()
            mock_db_session.return_value.__enter__.return_value = mock_session_instance
            
            # Create a test client
            client = self.app.test_client()
            
            # Set up a session with a user
            with client.session_transaction() as sess:
                sess['user'] = {'email': 'user@example.com', 'name': 'Regular User'}
            
            # Access the admin route
            response = client.get('/admin')
            
            # Verify that access was denied with a 403 status code
            self.assertEqual(response.status_code, 403)
            
            # Verify that is_admin was called with the correct email
            mock_manager.is_admin.assert_called_once_with(mock_user.email)
            
            # Verify that render_template was called with error.html
            mock_render.assert_called_once()
            self.assertEqual(mock_render.call_args[0][0], 'error.html')
    
    def test_require_admin_sets_admin_required_attribute(self):
        """Test that require_admin sets the __admin_required__ attribute on the decorated function."""
        # Define a function
        def test_func():
            return "Test Function"
        
        # Apply the decorator
        decorated_func = require_admin(test_func)
        
        # Check that the __admin_required__ attribute is set
        self.assertTrue(hasattr(decorated_func, '__admin_required__'))
        self.assertTrue(decorated_func.__admin_required__)
        
        # Check that the __auth_required__ attribute is also set
        self.assertTrue(hasattr(decorated_func, '__auth_required__'))
        self.assertTrue(decorated_func.__auth_required__)

if __name__ == '__main__':
    unittest.main()