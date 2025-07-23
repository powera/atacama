"""Tests for the archive service functionality."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from common.services.archive import ArchiveService, ArchiveConfig
from common.config.domain_config import DomainConfig


class TestArchiveService(unittest.TestCase):
    """Test cases for the ArchiveService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ArchiveConfig(
            excluded_domains=["localhost", "127.0.0.1", "example.com"]
        )
        self.service = ArchiveService(self.config)
        
        # Create mock domain configs
        self.archive_enabled_domain = DomainConfig(
            name="Shragafeivel",
            channels=["religion", "usconst"],
            theme="shragafeivel",
            auto_archive_enabled=True
        )
        
        self.archive_disabled_domain = DomainConfig(
            name="Main Site",
            channels=[],
            theme="default",
            auto_archive_enabled=False
        )

    def test_is_domain_archived(self):
        """Test domain archiving configuration."""
        self.assertTrue(self.service.is_domain_archived(self.archive_enabled_domain))
        self.assertFalse(self.service.is_domain_archived(self.archive_disabled_domain))

    def test_should_archive_url(self):
        """Test URL filtering logic."""
        # Valid URLs that should be archived
        self.assertTrue(self.service.should_archive_url("https://wikipedia.org/article"))
        self.assertTrue(self.service.should_archive_url("http://news.com/story"))
        
        # URLs that should be excluded
        self.assertFalse(self.service.should_archive_url("https://localhost/page"))
        self.assertFalse(self.service.should_archive_url("http://example.com/page"))
        self.assertFalse(self.service.should_archive_url("ftp://files.com/file"))
        self.assertFalse(self.service.should_archive_url(""))
        self.assertFalse(self.service.should_archive_url(None))

    @patch('constants.is_development_mode')
    @patch('requests.Session.get')
    def test_submit_url_to_archive_success(self, mock_get, mock_dev_mode):
        """Test successful URL submission to archive.org."""
        mock_dev_mode.return_value = False  # Production mode
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.service.submit_url_to_archive("https://example.org/page")
        self.assertTrue(result)
        mock_get.assert_called_once()

    @patch('constants.is_development_mode')
    @patch('requests.Session.get')
    def test_submit_url_to_archive_failure(self, mock_get, mock_dev_mode):
        """Test failed URL submission to archive.org."""
        mock_dev_mode.return_value = False  # Production mode
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = self.service.submit_url_to_archive("https://example.org/page")
        self.assertFalse(result)

    @patch('constants.is_development_mode')
    def test_submit_url_to_archive_debug_mode(self, mock_dev_mode):
        """Test URL submission in debug mode (should not make requests)."""
        mock_dev_mode.return_value = True  # Development mode
        
        result = self.service.submit_url_to_archive("https://example.org/page")
        self.assertTrue(result)  # Should return True without making requests

    @patch('constants.is_development_mode')
    def test_submit_urls_to_archive_debug_mode(self, mock_dev_mode):
        """Test multiple URL submission in debug mode."""
        mock_dev_mode.return_value = True  # Development mode
        
        urls = {"https://example.org/page1", "https://example.org/page2"}
        result = self.service.submit_urls_to_archive(urls)
        self.assertEqual(result, 2)  # Should return count without making requests

    @patch.object(ArchiveService, 'submit_urls_to_archive')
    def test_archive_urls_from_content_with_url_list(self, mock_submit):
        """Test archiving URLs from a provided list."""
        mock_submit.return_value = 2
        
        urls = ["https://wikipedia.org/wiki/Test", "http://news.com/story"]
        
        result = self.service.archive_urls_from_content(urls=urls)
        
        self.assertEqual(result, 2)
        mock_submit.assert_called_once()
        
        # Verify the URLs passed to submit_urls_to_archive
        submitted_urls = mock_submit.call_args[0][0]
        expected_urls = {
            "https://wikipedia.org/wiki/Test",
            "http://news.com/story"
        }
        self.assertEqual(submitted_urls, expected_urls)

    def test_archive_message_post_disabled_domain(self):
        """Test archiving message post for non-configured domain."""
        message_url = "https://shragafeivel.com/message/123"
        result = self.service.archive_message_post(message_url, self.archive_disabled_domain)
        self.assertEqual(result, 0)

    @patch.object(ArchiveService, 'submit_url_to_archive')
    def test_archive_message_post_enabled_domain(self, mock_submit):
        """Test archiving message post for configured domain."""
        mock_submit.return_value = True
        
        message_url = "https://shragafeivel.com/message/123"
        result = self.service.archive_message_post(message_url, self.archive_enabled_domain)
        
        self.assertEqual(result, 1)
        mock_submit.assert_called_once_with(message_url)


if __name__ == '__main__':
    unittest.main()