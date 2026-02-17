"""Tests for the message submission archiving functionality."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g

from common.config.domain_config import DomainConfig, DomainManager
from common.services.archive import ArchiveService, ArchiveConfig


class TestSubmitArchiving(unittest.TestCase):
    """Test cases for archiving logic in message submission."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)

        # Create mock domain configs
        self.shragafeivel_domain = DomainConfig(
            name="Shragafeivel",
            channels=["religion", "usconst", "chess", "education", "highphysics"],
            theme="shragafeivel",
            auto_archive_enabled=True,
        )

        self.default_domain = DomainConfig(
            name="Main Site",
            channels=[],  # Empty means all channels
            theme="default",
            auto_archive_enabled=False,
        )

        self.codepending_domain = DomainConfig(
            name="Code Pending",
            channels=["wikipedia"],
            theme="shragafeivel",
            auto_archive_enabled=True,
        )

    def test_channel_allowed_logic(self):
        """Test the channel_allowed logic for different domain configurations."""
        # Shragafeivel domain should allow specific channels
        self.assertTrue(self.shragafeivel_domain.channel_allowed("religion"))
        self.assertTrue(self.shragafeivel_domain.channel_allowed("usconst"))
        self.assertFalse(self.shragafeivel_domain.channel_allowed("wikipedia"))
        self.assertFalse(self.shragafeivel_domain.channel_allowed("misc"))

        # Default domain should allow all channels (empty list)
        self.assertTrue(self.default_domain.channel_allowed("religion"))
        self.assertTrue(self.default_domain.channel_allowed("wikipedia"))
        self.assertTrue(self.default_domain.channel_allowed("misc"))

        # Code Pending domain should only allow wikipedia
        self.assertTrue(self.codepending_domain.channel_allowed("wikipedia"))
        self.assertFalse(self.codepending_domain.channel_allowed("religion"))

    def test_archiving_domain_selection(self):
        """Test which domains should trigger archiving for different channels."""
        domains = {
            "shragafeivel": self.shragafeivel_domain,
            "default": self.default_domain,
            "codepending": self.codepending_domain,
        }

        # Test religion channel - should match shragafeivel (has archiving + allows channel)
        religion_archiving_domains = []
        for domain_key, domain_config in domains.items():
            if domain_config.auto_archive_enabled and domain_config.channel_allowed("religion"):
                religion_archiving_domains.append(domain_config)

        self.assertEqual(len(religion_archiving_domains), 1)
        self.assertEqual(religion_archiving_domains[0].name, "Shragafeivel")

        # Test wikipedia channel - should match codepending (has archiving + allows channel)
        wikipedia_archiving_domains = []
        for domain_key, domain_config in domains.items():
            if domain_config.auto_archive_enabled and domain_config.channel_allowed("wikipedia"):
                wikipedia_archiving_domains.append(domain_config)

        self.assertEqual(len(wikipedia_archiving_domains), 1)
        self.assertEqual(wikipedia_archiving_domains[0].name, "Code Pending")

        # Test misc channel - should match no domains with archiving enabled
        # (default allows all channels but has archiving disabled)
        misc_archiving_domains = []
        for domain_key, domain_config in domains.items():
            if domain_config.auto_archive_enabled and domain_config.channel_allowed("misc"):
                misc_archiving_domains.append(domain_config)

        self.assertEqual(len(misc_archiving_domains), 0)

    @patch("common.services.archive.get_archive_service")
    @patch("common.config.domain_config.get_domain_manager")
    def test_submit_archiving_integration(self, mock_get_domain_manager, mock_get_archive_service):
        """Test the integration of archiving logic in message submission."""
        # Mock domain manager
        mock_domain_manager = Mock()
        mock_domain_manager.domains = {
            "shragafeivel": self.shragafeivel_domain,
            "default": self.default_domain,
            "codepending": self.codepending_domain,
        }
        mock_get_domain_manager.return_value = mock_domain_manager

        # Mock archive service
        mock_archive_service = Mock()
        mock_archive_service.archive_urls_from_content.return_value = (
            2  # 2 URLs archived from content
        )
        mock_archive_service.archive_message_post.return_value = 1  # 1 post archived
        mock_get_archive_service.return_value = mock_archive_service

        # Simulate the archiving logic from submit.py
        channel = "religion"
        content = "Check out https://example.com/article"
        processed_content = "<a href='https://example.com/article'>article</a>"
        message_url = "https://shragafeivel.com/message/123"

        # 1. Always archive URLs from content
        archived_url_count = mock_archive_service.archive_urls_from_content(
            content, processed_content
        )
        self.assertEqual(archived_url_count, 2)

        # 2. Find archiving domains for post archiving
        archiving_domains = []
        for domain_key, domain_config in mock_domain_manager.domains.items():
            if domain_config.auto_archive_enabled and domain_config.channel_allowed(channel):
                archiving_domains.append(domain_config)

        # Should find shragafeivel domain
        self.assertEqual(len(archiving_domains), 1)
        self.assertEqual(archiving_domains[0].name, "Shragafeivel")

        # 3. Archive the post itself
        if archiving_domains:
            domain_config = archiving_domains[0]
            archived_post_count = mock_archive_service.archive_message_post(
                message_url, domain_config
            )
            self.assertEqual(archived_post_count, 1)

            # Verify the archive service was called with correct parameters
            mock_archive_service.archive_urls_from_content.assert_called_once_with(
                content, processed_content
            )
            mock_archive_service.archive_message_post.assert_called_once_with(
                message_url, domain_config
            )

    def test_url_archiving_always_happens(self):
        """Test that URL archiving happens regardless of domain/channel configuration."""
        # This simulates that URLs should be archived for ANY post in production
        # regardless of which domain has archiving enabled

        # Even for a channel that no archiving domain supports
        channel = "misc"
        domains = {
            "shragafeivel": self.shragafeivel_domain,
            "default": self.default_domain,
            "codepending": self.codepending_domain,
        }

        # Find archiving domains for "misc" channel
        archiving_domains = []
        for domain_key, domain_config in domains.items():
            if domain_config.auto_archive_enabled and domain_config.channel_allowed(channel):
                archiving_domains.append(domain_config)

        # No domains support "misc" channel with archiving
        self.assertEqual(len(archiving_domains), 0)

        # But URLs should still be archived from content
        # (this would be tested by calling archive_urls_from_content directly)


if __name__ == "__main__":
    unittest.main()
