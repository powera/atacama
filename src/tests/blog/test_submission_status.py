"""Tests for submission status domain link behavior."""

import unittest
from unittest.mock import Mock, patch

from blog.blueprints.admin import _build_submission_domain_links
from common.config.domain_config import DomainConfig


class TestSubmissionStatusDomainLinks(unittest.TestCase):
    """Test domain link generation for the submission status page."""

    @patch("blog.blueprints.admin.url_for")
    @patch("blog.blueprints.admin.get_domain_manager")
    def test_includes_only_domains_that_allow_channel(self, mock_get_domain_manager, mock_url_for):
        """Should include only domains serving the submitted channel."""
        mock_url_for.return_value = "/messages/17"
        mock_get_domain_manager.return_value = Mock(
            domains={
                "default": DomainConfig(name="Main Site", channels=[], theme="default"),
                "earlyversion": DomainConfig(
                    name="Early Version",
                    channels=["misc"],
                    theme="default",
                    domains=["earlyversion.com"],
                    https_enabled=True,
                ),
                "codepending": DomainConfig(
                    name="Code Pending",
                    channels=["wikipedia"],
                    theme="default",
                    domains=["codepending.com"],
                ),
            }
        )

        links = _build_submission_domain_links(
            channel="misc",
            message_id=17,
            current_domain="default",
            current_host="localhost",
            current_scheme="https",
        )

        self.assertEqual([d["domain_key"] for d in links], ["default", "earlyversion"])
        self.assertEqual(links[0]["url"], "https://localhost/messages/17")
        self.assertEqual(links[1]["url"], "https://earlyversion.com/messages/17")

    @patch("blog.blueprints.admin.url_for")
    @patch("blog.blueprints.admin.get_domain_manager")
    def test_preserves_unlinked_domain_when_host_unknown(
        self, mock_get_domain_manager, mock_url_for
    ):
        """Should show domain name even when no host can be linked."""
        mock_url_for.return_value = "/messages/9"
        mock_get_domain_manager.return_value = Mock(
            domains={
                "default": DomainConfig(name="Main Site", channels=[], theme="default"),
                "earlyversion": DomainConfig(
                    name="Early Version",
                    channels=["misc"],
                    theme="default",
                    domains=["earlyversion.com"],
                    https_enabled=True,
                ),
            }
        )

        links = _build_submission_domain_links(
            channel="misc",
            message_id=9,
            current_domain="earlyversion",
            current_host="",
            current_scheme="https",
        )

        self.assertIsNone(links[0]["url"])
        self.assertEqual(links[1]["url"], "https://earlyversion.com/messages/9")

    @patch("blog.blueprints.admin.url_for")
    @patch("blog.blueprints.admin.get_domain_manager")
    def test_uses_https_only_for_domains_configured_for_it(
        self, mock_get_domain_manager, mock_url_for
    ):
        """Should use HTTPS only for domains marked as HTTPS-enabled."""
        mock_url_for.return_value = "/messages/22"
        mock_get_domain_manager.return_value = Mock(
            domains={
                "default": DomainConfig(name="Main Site", channels=[], theme="default"),
                "pow3": DomainConfig(
                    name="Pow3",
                    channels=["tech"],
                    theme="pow3",
                    domains=["blog.pow3.com"],
                    https_enabled=True,
                ),
                "codepending": DomainConfig(
                    name="Code Pending",
                    channels=["tech"],
                    theme="default",
                    domains=["codepending.com"],
                    https_enabled=False,
                ),
            }
        )

        links = _build_submission_domain_links(
            channel="tech",
            message_id=22,
            current_domain="default",
            current_host="localhost",
            current_scheme="http",
        )

        self.assertEqual(links[0]["url"], "http://localhost/messages/22")
        self.assertEqual(links[1]["url"], "https://blog.pow3.com/messages/22")
        self.assertEqual(links[2]["url"], "http://codepending.com/messages/22")


if __name__ == "__main__":
    unittest.main()
