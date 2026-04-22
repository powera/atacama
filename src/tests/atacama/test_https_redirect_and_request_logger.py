"""Tests for HTTPS redirect behavior and request logger robustness."""

import unittest
from unittest.mock import patch

from flask import Flask

from atacama.server import before_request_handler
from common.base.request_logger import RequestLogger
from common.config.domain_config import DomainConfig, ThemeConfig
from common.config.language_config import LanguageConfig


class HttpsRedirectTests(unittest.TestCase):
    """Test HTTPS redirect behavior in before_request_handler."""

    def setUp(self):
        self.app = Flask(__name__)

    def test_no_app_redirect_when_forwarded_proto_present(self):
        """If NGINX provides X-Forwarded-Proto, app should not force redirect."""
        domain_config = DomainConfig(
            name="Pow3",
            channels=[],
            theme="pow3",
            domains=["blog.pow3.com"],
            https_enabled=True,
        )
        theme_config = ThemeConfig(name="Pow3", css_files=[], layout="pow3")
        language_config = LanguageConfig(name="English", code="en", subdomains=[])

        with (
            self.app.test_request_context(
                "/messages/22",
                base_url="http://blog.pow3.com",
                headers={"X-Forwarded-Proto": "http"},
            ),
            patch("atacama.server.get_domain_manager") as mock_domain_manager,
            patch("atacama.server.get_language_manager") as mock_language_manager,
        ):
            mock_domain_manager.return_value.get_domain_for_host.return_value = "pow3"
            mock_domain_manager.return_value.get_domain_config.return_value = domain_config
            mock_domain_manager.return_value.get_theme_config.return_value = theme_config
            mock_language_manager.return_value.get_language_from_host.return_value = "english"
            mock_language_manager.return_value.get_language_config.return_value = language_config

            response = before_request_handler()

        self.assertIsNone(response)

    def test_no_app_redirect_without_forwarded_proto(self):
        """App should not force HTTPS redirects; NGINX is responsible for that."""
        domain_config = DomainConfig(
            name="Pow3",
            channels=[],
            theme="pow3",
            domains=["blog.pow3.com"],
            https_enabled=True,
        )
        theme_config = ThemeConfig(name="Pow3", css_files=[], layout="pow3")
        language_config = LanguageConfig(name="English", code="en", subdomains=[])

        with (
            self.app.test_request_context(
                "/messages/22",
                base_url="http://blog.pow3.com",
            ),
            patch("atacama.server.get_domain_manager") as mock_domain_manager,
            patch("atacama.server.get_language_manager") as mock_language_manager,
        ):
            mock_domain_manager.return_value.get_domain_for_host.return_value = "pow3"
            mock_domain_manager.return_value.get_domain_config.return_value = domain_config
            mock_domain_manager.return_value.get_theme_config.return_value = theme_config
            mock_language_manager.return_value.get_language_from_host.return_value = "english"
            mock_language_manager.return_value.get_language_config.return_value = language_config

            response = before_request_handler()

        self.assertIsNone(response)


class RequestLoggerTests(unittest.TestCase):
    """Test RequestLogger edge cases."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"

        @self.app.route("/ping")
        def ping():
            return "pong"

    def test_missing_request_start_time_does_not_error(self):
        """after_request should not fail when request_start_time is absent."""
        request_logger = RequestLogger(self.app)
        self.assertIsNotNone(request_logger)

        # Simulate another before_request handler that short-circuits execution.
        self.app.before_request_funcs[None].insert(0, lambda: ("redirect", 301))

        with self.app.test_client() as client:
            response = client.get("/ping")

        self.assertEqual(response.status_code, 301)


if __name__ == "__main__":
    unittest.main()
