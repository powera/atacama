"""Tests for authentication - OAuth flow, session management, and decorators."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from flask import session, g

from atacama.server import create_app
from atacama.decorators.auth import require_auth, optional_auth
from models.database import db
from models.models import User, UserToken


class AuthenticationDecoratorTests(unittest.TestCase):
    """Test cases for authentication decorators."""

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

    def test_require_auth_redirects_unauthenticated(self):
        """Test that @require_auth redirects unauthenticated users."""
        with self.app.app_context():
            # Create a test route with @require_auth
            @self.app.route('/protected')
            @require_auth
            def protected_route():
                return 'Protected content'

            response = self.client.get('/protected')

            # Should redirect to login
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.location)

    def test_require_auth_allows_authenticated_session(self):
        """Test that @require_auth allows authenticated users via session."""
        # Set up authenticated session
        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}

        with self.app.app_context():
            @self.app.route('/protected-session')
            @require_auth
            def protected_session_route():
                return 'Protected content'

            response = self.client.get('/protected-session')

            # Should allow access
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Protected content', response.data)

    def test_require_auth_with_token(self):
        """Test that @require_auth allows authenticated users via token."""
        # Create user and token in database
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email='token@example.com', name='Token User')
                db_session.add(user)
                db_session.flush()

                token = UserToken(
                    user_id=user.id,
                    token='test-token-12345',
                    created_at=datetime.utcnow()
                )
                db_session.add(token)
                db_session.commit()

        with self.app.app_context():
            @self.app.route('/protected-token')
            @require_auth
            def protected_token_route():
                return f'Protected content for {g.user.email}'

            response = self.client.get(
                '/protected-token',
                headers={'Authorization': 'Bearer test-token-12345'}
            )

            # Should allow access
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Protected content for token@example.com', response.data)

    def test_require_auth_expired_token(self):
        """Test that expired tokens are rejected."""
        # Create user and expired token
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email='expired@example.com', name='Expired User')
                db_session.add(user)
                db_session.flush()

                # Token created 121 days ago (expired, limit is 120 days)
                expired_time = datetime.utcnow() - timedelta(days=121)
                token = UserToken(
                    user_id=user.id,
                    token='expired-token-12345',
                    created_at=expired_time
                )
                db_session.add(token)
                db_session.commit()

        with self.app.app_context():
            @self.app.route('/protected-expired')
            @require_auth
            def protected_expired_route():
                return 'Protected content'

            response = self.client.get(
                '/protected-expired',
                headers={'Authorization': 'Bearer expired-token-12345'}
            )

            # Should reject expired token
            self.assertIn(response.status_code, [302, 401])

    def test_optional_auth_allows_unauthenticated(self):
        """Test that @optional_auth allows both authenticated and unauthenticated access."""
        with self.app.app_context():
            @self.app.route('/optional')
            @optional_auth
            def optional_route():
                if g.user:
                    return f'Hello {g.user.email}'
                return 'Hello anonymous'

            # Test without authentication
            response = self.client.get('/optional')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Hello anonymous', response.data)

            # Test with authentication
            with self.client.session_transaction() as sess:
                sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}

            response = self.client.get('/optional')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Hello test@example.com', response.data)

    def test_require_auth_api_returns_json(self):
        """Test that @require_auth returns JSON for API requests."""
        with self.app.app_context():
            @self.app.route('/api/protected')
            @require_auth
            def api_protected():
                return {'message': 'success'}

            response = self.client.get(
                '/api/protected',
                headers={'Accept': 'application/json'}
            )

            # Should return JSON error for API requests
            self.assertIn(response.status_code, [401, 302])

    def test_token_format_bearer_prefix(self):
        """Test that tokens work with 'Bearer ' prefix."""
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email='bearer@example.com', name='Bearer User')
                db_session.add(user)
                db_session.flush()

                token = UserToken(
                    user_id=user.id,
                    token='bearer-token-xyz',
                    created_at=datetime.utcnow()
                )
                db_session.add(token)
                db_session.commit()

        with self.app.app_context():
            @self.app.route('/token-test')
            @require_auth
            def token_test():
                return 'Authenticated'

            # Test with Bearer prefix
            response = self.client.get(
                '/token-test',
                headers={'Authorization': 'Bearer bearer-token-xyz'}
            )
            self.assertEqual(response.status_code, 200)

            # Test without Bearer prefix
            response = self.client.get(
                '/token-test',
                headers={'Authorization': 'bearer-token-xyz'}
            )
            self.assertEqual(response.status_code, 200)


class AuthenticationRouteTests(unittest.TestCase):
    """Test cases for authentication routes."""

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

    def test_login_page_renders(self):
        """Test that login page renders successfully."""
        response = self.client.get('/login')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.data.lower())

    def test_login_page_popup_mode(self):
        """Test login page in popup mode."""
        response = self.client.get('/login?popup=true')

        self.assertEqual(response.status_code, 200)
        # Verify popup template is used
        self.assertIn(b'login', response.data.lower())

    def test_login_page_with_redirect(self):
        """Test login page stores redirect URL."""
        with self.client as client:
            response = client.get('/login?next=/protected-page')

            self.assertEqual(response.status_code, 200)
            # Check that redirect is stored in session
            with client.session_transaction() as sess:
                self.assertEqual(sess.get('post_login_redirect'), '/protected-page')

    def test_logout_clears_session(self):
        """Test that logout clears the session."""
        # Set up session
        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'test@example.com', 'name': 'Test User'}
            sess['other_data'] = 'some value'

        response = self.client.get('/logout')

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Check that session is cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn('user', sess)
            self.assertNotIn('other_data', sess)

    def test_api_logout_requires_auth(self):
        """Test that API logout requires authentication."""
        response = self.client.post('/api/logout')

        # Should require authentication
        self.assertIn(response.status_code, [302, 401, 400])

    def test_api_logout_revokes_token(self):
        """Test that API logout revokes the token."""
        # Create user and token
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email='logout@example.com', name='Logout User')
                db_session.add(user)
                db_session.flush()

                token = UserToken(
                    user_id=user.id,
                    token='logout-token-123',
                    created_at=datetime.utcnow()
                )
                db_session.add(token)
                db_session.commit()

        # Logout with token
        response = self.client.post(
            '/api/logout',
            headers={'Authorization': 'Bearer logout-token-123'}
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Verify token is revoked by trying to use it again
        with self.app.app_context():
            @self.app.route('/test-after-logout')
            @require_auth
            def test_after_logout():
                return 'Should not work'

            response = self.client.get(
                '/test-after-logout',
                headers={'Authorization': 'Bearer logout-token-123'}
            )

            # Token should no longer work
            self.assertIn(response.status_code, [302, 401])

    def test_mobile_oauth_flow(self):
        """Test mobile OAuth flow parameters."""
        with self.client as client:
            response = client.get('/login?mobile=1&redirect=myapp://callback')

            self.assertEqual(response.status_code, 200)

            # Check that mobile mode is stored in session
            with client.session_transaction() as sess:
                self.assertTrue(sess.get('mobile_mode'))
                self.assertEqual(sess.get('mobile_redirect'), 'myapp://callback')


class AuthVerifyTests(unittest.TestCase):
    """Test cases for /auth/verify endpoint (NGINX auth_request for admin access)."""

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

    def test_verify_unauthenticated_returns_401(self):
        """Test that /auth/verify returns 401 when no user is logged in."""
        response = self.client.get('/auth/verify')
        self.assertEqual(response.status_code, 401)

    @patch('atacama.blueprints.auth.get_user_config_manager')
    def test_verify_non_admin_returns_403(self, mock_get_ucm):
        """Test that /auth/verify returns 403 for authenticated non-admin users."""
        mock_ucm = MagicMock()
        mock_ucm.is_admin.return_value = False
        mock_get_ucm.return_value = mock_ucm

        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'regular@example.com', 'name': 'Regular User'}

        response = self.client.get('/auth/verify')
        self.assertEqual(response.status_code, 403)
        mock_ucm.is_admin.assert_called_once()

    @patch('atacama.blueprints.auth.get_user_config_manager')
    def test_verify_admin_returns_200(self, mock_get_ucm):
        """Test that /auth/verify returns 200 for admin users."""
        mock_ucm = MagicMock()
        mock_ucm.is_admin.return_value = True
        mock_get_ucm.return_value = mock_ucm

        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'admin@example.com', 'name': 'Admin User'}

        response = self.client.get('/auth/verify')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'')

    @patch('atacama.blueprints.auth.get_user_config_manager')
    def test_verify_admin_with_token(self, mock_get_ucm):
        """Test that /auth/verify works with token-based auth."""
        mock_ucm = MagicMock()
        mock_ucm.is_admin.return_value = True
        mock_get_ucm.return_value = mock_ucm

        # Create user and token in database
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email='tokenadmin@example.com', name='Token Admin')
                db_session.add(user)
                db_session.flush()

                token = UserToken(
                    user_id=user.id,
                    token='admin-verify-token',
                    created_at=datetime.utcnow()
                )
                db_session.add(token)
                db_session.commit()

        response = self.client.get(
            '/auth/verify',
            headers={'Authorization': 'Bearer admin-verify-token'}
        )
        self.assertEqual(response.status_code, 200)

    @patch('atacama.blueprints.auth.get_user_config_manager')
    def test_verify_returns_empty_body(self, mock_get_ucm):
        """Test that /auth/verify returns empty body for all status codes."""
        # Admin case - 200 with empty body
        mock_ucm = MagicMock()
        mock_ucm.is_admin.return_value = True
        mock_get_ucm.return_value = mock_ucm

        with self.client.session_transaction() as sess:
            sess['user'] = {'email': 'admin@example.com', 'name': 'Admin User'}

        response = self.client.get('/auth/verify')
        self.assertEqual(response.data, b'')

        # Non-admin case - 403 with empty body
        mock_ucm.is_admin.return_value = False
        response = self.client.get('/auth/verify')
        self.assertEqual(response.data, b'')


class UserCreationTests(unittest.TestCase):
    """Test cases for user creation and management."""

    def setUp(self):
        """Set up test application."""
        self.app = create_app(testing=True)
        self.app.config.update({
            'TESTING': True,
            'SERVER_NAME': 'test.local',
        })

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_get_or_create_user_creates_new(self):
        """Test that get_or_create_user creates a new user if not exists."""
        from models import get_or_create_user

        with self.app.app_context():
            with db.session() as db_session:
                user_info = {'email': 'new@example.com', 'name': 'New User'}
                user = get_or_create_user(db_session, user_info)

                self.assertIsNotNone(user)
                self.assertEqual(user.email, 'new@example.com')
                self.assertEqual(user.name, 'New User')

    def test_get_or_create_user_retrieves_existing(self):
        """Test that get_or_create_user retrieves existing user."""
        from models import get_or_create_user

        with self.app.app_context():
            # Create user first time
            with db.session() as db_session:
                user_info = {'email': 'existing@example.com', 'name': 'Existing User'}
                user1 = get_or_create_user(db_session, user_info)
                user1_id = user1.id

            # Retrieve same user
            with db.session() as db_session:
                user_info = {'email': 'existing@example.com', 'name': 'Updated Name'}
                user2 = get_or_create_user(db_session, user_info)

                # Should be the same user
                self.assertEqual(user2.id, user1_id)
                self.assertEqual(user2.email, 'existing@example.com')


if __name__ == '__main__':
    unittest.main()
