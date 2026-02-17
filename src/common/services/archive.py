"""Archive.org integration service for automatic URL archiving."""

import os
import re
import requests  # type: ignore[import-untyped]
import time
from typing import List, Set, Optional
from urllib.parse import urlparse
from dataclasses import dataclass

import constants
from common.base.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ArchiveConfig:
    """Configuration for archive.org integration."""

    excluded_domains: Optional[List[str]] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None

    def __post_init__(self):
        if self.excluded_domains is None:
            self.excluded_domains = []

        # Load credentials from environment if not provided
        if self.access_key is None:
            self.access_key = os.getenv("SAVEPAGENOW_ACCESS_KEY")
        if self.secret_key is None:
            self.secret_key = os.getenv("SAVEPAGENOW_SECRET_KEY")


class ArchiveService:
    """Service for submitting URLs to archive.org for archiving."""

    ARCHIVE_ORG_SAVE_URL = "https://web.archive.org/save"
    URL_PATTERN = re.compile(r"https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+")

    def __init__(self, config: ArchiveConfig):
        """
        Initialize the archive service.

        :param config: Archive configuration
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Atacama-Archive-Bot/1.0 (https://github.com/atacama/atacama)"}
        )

        # Set up authentication if credentials are available
        if self.config.access_key and self.config.secret_key:
            auth_string = f"LOW {self.config.access_key}:{self.config.secret_key}"
            self.session.headers.update({"Authorization": auth_string})
            logger.info("Archive.org authentication configured")
        else:
            logger.info("Archive.org running in anonymous mode (rate limited to 3 requests/minute)")

    def is_domain_archived(self, domain_config) -> bool:
        """
        Check if a domain should have its content archived.

        :param domain_config: DomainConfig object to check
        :return: True if domain should be archived
        """
        return getattr(domain_config, "auto_archive_enabled", False)

    def should_archive_url(self, url: str) -> bool:
        """
        Check if a URL should be archived based on configuration.

        :param url: URL to check
        :return: True if URL should be archived
        """
        if not url or not url.startswith(("http://", "https://")):
            return False

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]

            # Check if domain is in excluded list
            for excluded in self.config.excluded_domains or []:
                if domain == excluded.lower() or domain.endswith("." + excluded.lower()):
                    return False

            return True
        except Exception as e:
            logger.warning(f"Error parsing URL {url}: {e}")
            return False

    def extract_urls_from_text(self, text: str) -> Set[str]:
        """
        Extract all URLs from text content.

        :param text: Text content to search for URLs
        :return: Set of unique URLs found
        """
        if not text:
            return set()

        urls = set()

        # Find all URLs using regex
        matches = self.URL_PATTERN.findall(text)
        for match in matches:
            # Clean up the URL (remove trailing punctuation that might be captured)
            url = match.rstrip(".,;:!?)")
            if self.should_archive_url(url):
                urls.add(url)

        return urls

    def extract_urls_from_html(self, html_content: str) -> Set[str]:
        """
        Extract URLs from HTML content (from href attributes).

        :param html_content: HTML content to search for URLs
        :return: Set of unique URLs found
        """
        if not html_content:
            return set()

        urls = set()

        # Extract URLs from href attributes
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        href_matches = href_pattern.findall(html_content)

        for url in href_matches:
            if self.should_archive_url(url):
                urls.add(url)

        # Also extract plain URLs from text content
        text_urls = self.extract_urls_from_text(html_content)
        urls.update(text_urls)

        return urls

    def submit_url_to_archive(self, url: str) -> bool:
        """
        Submit a single URL to archive.org for archiving using the Save Page Now API.

        :param url: URL to archive
        :return: True if submission was successful
        """
        if not self.should_archive_url(url):
            logger.debug(f"Skipping URL archiving for {url} (excluded or invalid)")
            return False

        # In development mode, just log what would be archived without making requests
        if constants.is_development_mode():
            logger.info(f"[DEBUG MODE] Would submit URL to archive.org: {url}")
            return True

        try:
            logger.info(f"Submitting URL to archive.org: {url}")

            # Use POST request with form data as required by the Save Page Now API
            data = {
                "url": url,
                "capture_all": "on",  # Capture all page resources
                "capture_screenshot": "on",  # Capture screenshot
            }

            response = self.session.post(self.ARCHIVE_ORG_SAVE_URL, data=data, timeout=60)

            # Archive.org may return various status codes for successful submissions
            if response.status_code in [200, 302]:
                # Check if we got a successful response or redirect to archived page
                if (
                    "web.archive.org/web/" in response.url
                    or "web.archive.org/web/" in response.text
                ):
                    logger.info(f"Successfully submitted URL to archive.org: {url}")
                    return True
                else:
                    logger.warning(
                        f"Archive.org submission unclear for URL: {url}, response: {response.status_code}"
                    )
                    return False
            elif response.status_code == 429:
                logger.warning(
                    f"Rate limited by archive.org for URL: {url}. Consider adding authentication or increasing delays."
                )
                return False
            else:
                logger.warning(f"Archive.org returned status {response.status_code} for URL: {url}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"Timeout submitting URL to archive.org: {url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error submitting URL to archive.org: {url}, error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error submitting URL to archive.org: {url}, error: {e}")
            return False

    def submit_urls_to_archive(
        self, urls: Set[str], delay_between_requests: Optional[float] = None
    ) -> int:
        """
        Submit multiple URLs to archive.org for archiving.

        :param urls: Set of URLs to archive
        :param delay_between_requests: Delay in seconds between requests to be respectful
                                     (defaults to 20s for anonymous, 10s for authenticated)
        :return: Number of successfully submitted URLs
        """
        if not urls:
            return 0

        # Set default delay based on authentication status
        if delay_between_requests is None:
            if self.config.access_key and self.config.secret_key:
                delay_between_requests = 10.0  # Authenticated: 6 requests/minute = 10s delay
            else:
                delay_between_requests = 20.0  # Anonymous: 3 requests/minute = 20s delay

        # In development mode, log all URLs at once without delays
        if constants.is_development_mode():
            logger.info(f"[DEBUG MODE] Would submit {len(urls)} URLs to archive.org:")
            for url in urls:
                logger.info(f"[DEBUG MODE]   - {url}")
            return len(urls)  # Return success count as if all were submitted

        successful_submissions = 0

        for i, url in enumerate(urls):
            if i > 0:
                # Add delay between requests to respect rate limits
                logger.debug(f"Waiting {delay_between_requests}s before next archive request...")
                time.sleep(delay_between_requests)

            if self.submit_url_to_archive(url):
                successful_submissions += 1

        logger.info(
            f"Archive submission complete: {successful_submissions}/{len(urls)} URLs successfully submitted"
        )
        return successful_submissions

    def archive_urls_from_content(
        self,
        urls: Optional[List[str]] = None,
        content: Optional[str] = None,
        processed_content: Optional[str] = None,
    ) -> int:
        """
        Archive all URLs found in message content (always in production, regardless of domain/channel).

        :param urls: List of URLs to archive, or None to extract from content
        :param content: Raw message content to scan for URLs (fallback if urls is None)
        :param processed_content: Optional processed HTML content to also scan for URLs (fallback)
        :return: Number of URLs successfully submitted for archiving
        """
        url_set = set()

        if urls is not None:
            # Use provided list of URLs
            url_set.update(urls)
        else:
            # Fallback to old behavior - extract from content
            if content:
                url_set.update(self.extract_urls_from_text(content))

            if processed_content:
                url_set.update(self.extract_urls_from_html(processed_content))

        if not url_set:
            logger.debug("No URLs found in message content")
            return 0

        logger.info(f"Found {len(url_set)} URLs to archive from message content")
        return self.submit_urls_to_archive(url_set)

    def archive_message_post(self, message_url: str, domain_config) -> int:
        """
        Archive the message post itself if the domain is configured for archiving.

        :param message_url: URL of the message post to archive
        :param domain_config: DomainConfig object for the domain
        :return: Number of URLs successfully submitted for archiving (0 or 1)
        """
        if not self.is_domain_archived(domain_config):
            logger.debug(f"Domain {domain_config.name} not configured for post archiving")
            return 0

        if not self.should_archive_url(message_url):
            logger.debug(f"Message URL {message_url} excluded from archiving")
            return 0

        logger.info(f"Archiving message post for domain {domain_config.name}: {message_url}")
        if self.submit_url_to_archive(message_url):
            return 1
        return 0


# Global archive service instance
_archive_service: Optional[ArchiveService] = None


def init_archive_service(config: ArchiveConfig) -> ArchiveService:
    """
    Initialize global archive service instance.

    :param config: Archive configuration
    :return: Archive service instance
    """
    global _archive_service
    _archive_service = ArchiveService(config)
    return _archive_service


def get_archive_service() -> Optional[ArchiveService]:
    """
    Get global archive service instance.

    :return: Archive service instance or None if not initialized
    """
    return _archive_service
