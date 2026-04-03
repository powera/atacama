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
            scheme="https",
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
                ),
            }
        )

        links = _build_submission_domain_links(
            channel="misc",
            message_id=9,
            current_domain="earlyversion",
            current_host="",
            scheme="https",
        )

        self.assertIsNone(links[0]["url"])
        self.assertEqual(links[1]["url"], "https://earlyversion.com/messages/9")


if __name__ == "__main__":
    unittest.main()
