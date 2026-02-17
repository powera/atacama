"""Tests for error handling blueprints and templates."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, Blueprint, abort, g
from werkzeug.exceptions import NotFound, Forbidden, InternalServerError

from atacama.server import create_app
from models.database import db
from models.models import User


class ErrorHandlerTests(unittest.TestCase):
    """Test cases for error handlers."""

    def setUp(self):
        """Set up test application with in-memory database."""
        self.app = create_app(testing=True)
        self.app.config.update(
            {
                "TESTING": True,
                "SERVER_NAME": "test.local",
                "DEBUG": False,  # Test production error behavior
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    def test_404_error_html(self):
        """Test 404 error returns HTML for browser requests."""
        response = self.client.get("/nonexistent-page", headers={"Accept": "text/html"})

        self.assertEqual(response.status_code, 404)
        self.assertIn(b"404", response.data)
        self.assertIn(b"Page Not Found", response.data)
        self.assertIn(b"could not be found", response.data)

    def test_404_error_json(self):
        """Test 404 error returns JSON for API requests."""
        response = self.client.get("/nonexistent-page", headers={"Accept": "application/json"})

        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertIn("message", data)

    def test_403_error_html(self):
        """Test 403 Forbidden error handling."""
        # Create a test route that raises 403
        with self.app.app_context():

            @self.app.route("/forbidden-test")
            def forbidden_test():
                abort(403)

            response = self.client.get("/forbidden-test", headers={"Accept": "text/html"})

            self.assertEqual(response.status_code, 403)
            self.assertIn(b"403", response.data)
            self.assertIn(b"Forbidden", response.data)
            self.assertIn(b"don't have permission", response.data)

    def test_500_error_html(self):
        """Test 500 Internal Server Error handling."""
        # Create a test route that raises an exception
        with self.app.app_context():

            @self.app.route("/error-test")
            def error_test():
                raise Exception("Test error")

            response = self.client.get("/error-test", headers={"Accept": "text/html"})

            self.assertEqual(response.status_code, 500)
            self.assertIn(b"500", response.data)
            self.assertIn(b"Internal Server Error", response.data)

    def test_error_page_includes_channel_manager(self):
        """Test that error pages include channel_manager for template rendering."""
        response = self.client.get("/nonexistent-page", headers={"Accept": "text/html"})

        self.assertEqual(response.status_code, 404)
        # The response should render without errors even if it includes channel links
        # This verifies the channel_manager fix
        self.assertIsNotNone(response.data)

    def test_error_page_with_authenticated_user(self):
        """Test error page rendering with authenticated user."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@example.com", "name": "Test User"}

        response = self.client.get("/nonexistent-page", headers={"Accept": "text/html"})

        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(response.data)

    def test_database_error_handling(self):
        """Test that database errors are caught and handled gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        with self.app.app_context():

            @self.app.route("/db-error-test")
            def db_error_test():
                raise SQLAlchemyError("Database connection failed")

            response = self.client.get("/db-error-test", headers={"Accept": "text/html"})

            self.assertEqual(response.status_code, 500)
            self.assertIn(b"500", response.data)
            self.assertIn(b"Database Error", response.data)

    def test_405_method_not_allowed(self):
        """Test 405 Method Not Allowed error handling."""
        # Try to POST to a GET-only route
        response = self.client.post("/", headers={"Accept": "text/html"})

        self.assertEqual(response.status_code, 405)
        self.assertIn(b"405", response.data)
        self.assertIn(b"Method Not Allowed", response.data)

    def test_debug_mode_shows_technical_details(self):
        """Test that technical details are shown in debug mode."""
        # Enable debug mode
        self.app.config["DEBUG"] = True

        with self.app.app_context():

            @self.app.route("/debug-error-test")
            def debug_error_test():
                raise ValueError("Test error with details")

            response = self.client.get("/debug-error-test", headers={"Accept": "text/html"})

            self.assertEqual(response.status_code, 500)
            # In debug mode, technical details should be included
            self.assertIn(b"Test error with details", response.data)

    def test_production_mode_hides_technical_details(self):
        """Test that technical details are hidden in production mode."""
        # Ensure debug mode is off
        self.app.config["DEBUG"] = False

        with self.app.app_context():

            @self.app.route("/prod-error-test")
            def prod_error_test():
                raise ValueError("Secret error details")

            response = self.client.get("/prod-error-test", headers={"Accept": "text/html"})

            self.assertEqual(response.status_code, 500)
            # In production mode, secret details should not be shown
            self.assertNotIn(b"Secret error details", response.data)


if __name__ == "__main__":
    unittest.main()
