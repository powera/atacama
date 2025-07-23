"""Archive.org integration service for automatic URL archiving."""

import re
import requests
import time
from typing import List, Set, Optional
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass

import constants
from common.base.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ArchiveConfig:
    """Configuration for archive.org integration."""
    excluded_domains: List[str] = None
    
    def __post_init__(self):
        if self.excluded_domains is None:
            self.excluded_domains = []

class ArchiveService:
    """Service for submitting URLs to archive.org for archiving."""
    
    ARCHIVE_ORG_SAVE_URL = "https://web.archive.org/save/"
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')
    
    def __init__(self, config: ArchiveConfig):
        """
        Initialize the archive service.
        
        :param config: Archive configuration
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Atacama-Archive-Bot/1.0 (https://github.com/atacama/atacama)'
        })
        
    def is_domain_archived(self, domain_config) -> bool:
        """
        Check if a domain should have its content archived.
        
        :param domain_config: DomainConfig object to check
        :return: True if domain should be archived
        """
        return getattr(domain_config, 'auto_archive_enabled', False)
    
    def should_archive_url(self, url: str) -> bool:
        """
        Check if a URL should be archived based on configuration.
        
        :param url: URL to check
        :return: True if URL should be archived
        """
        if not url or not url.startswith(('http://', 'https://')):
            return False
            
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]
                
            # Check if domain is in excluded list
            for excluded in self.config.excluded_domains:
                if domain == excluded.lower() or domain.endswith('.' + excluded.lower()):
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
            url = match.rstrip('.,;:!?)')
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
        Submit a single URL to archive.org for archiving.
        
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
            archive_url = urljoin(self.ARCHIVE_ORG_SAVE_URL, url)
            logger.info(f"Submitting URL to archive.org: {url}")
            
            response = self.session.get(archive_url, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Successfully submitted URL to archive.org: {url}")
                return True
            else:
                logger.warning(f"Archive.org returned status {response.status_code} for URL: {url}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error submitting URL to archive.org: {url}, error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error submitting URL to archive.org: {url}, error: {e}")
            return False
    
    def submit_urls_to_archive(self, urls: Set[str], delay_between_requests: float = 1.0) -> int:
        """
        Submit multiple URLs to archive.org for archiving.
        
        :param urls: Set of URLs to archive
        :param delay_between_requests: Delay in seconds between requests to be respectful
        :return: Number of successfully submitted URLs
        """
        if not urls:
            return 0
        
        # In development mode, log all URLs at once without delays
        if constants.is_development_mode():
            logger.info(f"[DEBUG MODE] Would submit {len(urls)} URLs to archive.org:")
            for url in urls:
                logger.info(f"[DEBUG MODE]   - {url}")
            return len(urls)  # Return success count as if all were submitted
            
        successful_submissions = 0
        
        for i, url in enumerate(urls):
            if i > 0:
                # Add delay between requests to be respectful to archive.org
                time.sleep(delay_between_requests)
                
            if self.submit_url_to_archive(url):
                successful_submissions += 1
                
        logger.info(f"Archive submission complete: {successful_submissions}/{len(urls)} URLs successfully submitted")
        return successful_submissions
    
    def archive_urls_from_content(self, urls=None, content: str = None, processed_content: str = None) -> int:
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