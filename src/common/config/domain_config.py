"""Domain configuration management for Atacama."""

import os
from pathlib import Path
import tomli
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import constants
from common.base.logging_config import get_logger
from common.services.archive import ArchiveConfig

logger = get_logger(__name__)

@dataclass
class ThemeConfig:
    """Theme configuration data structure."""
    name: str
    css_files: List[str]
    layout: str = "default"
    banner: bool = False
    
@dataclass
class DomainConfig:
    """Domain configuration data structure."""
    name: str
    channels: List[str]  # Empty list means all channels
    theme: str
    description: Optional[str] = None
    domains: List[str] = None  # List of hostnames that map to this domain config
    auto_archive_enabled: bool = False  # Whether to enable auto-archiving for this domain
    
    @property
    def allows_all_channels(self) -> bool:
        """Whether the domain allows all channels."""
        return len(self.channels) == 0
    
    def channel_allowed(self, channel_name: str) -> bool:
        """
        Check if a channel is allowed on this domain.
        
        :param channel_name: Name of the channel to check
        :return: True if allowed, False otherwise
        """
        return self.allows_all_channels or channel_name in self.channels

class DomainManager:
    """Manages domain configuration and validation."""
    
    def __init__(self, config_path: str):
        """
        Initialize domain manager with configuration file.
        
        :param config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.domains: Dict[str, DomainConfig] = {}
        self.themes: Dict[str, ThemeConfig] = {}
        self.host_to_domain: Dict[str, str] = {}  # Maps hosts to domain configs
        self.default_domain = "default"
        self.archive_config: Optional[ArchiveConfig] = None
        self._load_config()
        
    def _load_config(self) -> None:
        """Load and validate domain configuration from TOML file."""
        try:
            logger.info(f"Loading domain configuration from {self.config_path}")
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)
            
            # Load archive configuration
            archive_config = config.get('archive', {})
            self.archive_config = ArchiveConfig(
                excluded_domains=archive_config.get('excluded_domains', [])
            )
            
            # Load theme configurations
            themes_config = config.get('themes', {})
            for name, settings in themes_config.items():
                self.themes[name] = ThemeConfig(
                    name=settings.get('name', name),
                    css_files=settings.get('css_files', []),
                    layout=settings.get('layout', 'default'),
                    banner=settings.get('banner', False)
                )
                
            # Load domain configurations
            domains_config = config.get('domains', {})
            for domain_key, settings in domains_config.items():
                self.domains[domain_key] = DomainConfig(
                    name=settings.get('name', domain_key),
                    channels=settings.get('channels', []),
                    theme=settings.get('theme', 'default'),
                    description=settings.get('description'),
                    domains=settings.get('domains', []),
                    auto_archive_enabled=settings.get('auto_archive_enabled', False)
                )
                
                # Map each hostname to this domain config
                if settings.get('domains'):
                    for hostname in settings.get('domains', []):
                        if hostname in self.host_to_domain:
                            # Found duplicate hostname
                            existing_domain = self.host_to_domain[hostname]
                            logger.error(f"Duplicate hostname '{hostname}' found in domains '{domain_key}' and '{existing_domain}'")
                            raise ValueError(f"Duplicate hostname '{hostname}' in multiple domain configurations")
                        self.host_to_domain[hostname] = domain_key
                        
            # Validate configuration
            self._validate_config()
            
            # Log successful initialization
            logger.info(f"Domain configuration loaded successfully: {len(self.domains)} domains, {len(self.themes)} themes")
            for domain_key, config in self.domains.items():
                channel_info = "all channels" if config.allows_all_channels else f"{len(config.channels)} channels"
                logger.info(f"  Domain '{domain_key}': {config.name}, theme: {config.theme}, {channel_info}")
                
        except Exception as e:
            logger.error(f"Error loading domain configuration: {str(e)}")
            raise
            
    def _validate_config(self) -> None:
        """Validate domain configuration for consistency."""
        if not self.domains:
            raise ValueError("No domains defined in configuration")
            
        if self.default_domain not in self.domains:
            raise ValueError(f"Default domain '{self.default_domain}' not found in domain list")
            
        # Validate theme references
        for domain_key, domain_config in self.domains.items():
            if domain_config.theme not in self.themes:
                raise ValueError(f"Theme '{domain_config.theme}' referenced by domain '{domain_key}' not found")
                
    def get_domain_for_host(self, host: str) -> str:
        """
        Get domain key for a host name.
        
        :param host: Host name from request
        :return: Domain key from config, or default if not found
        """
        # Strip port from host if present
        if ':' in host:
            host = host.split(':', 1)[0]
        
        # Check the exact host first
        if host in self.host_to_domain:
            domain_key = self.host_to_domain[host]
            logger.debug(f"Direct host match found: {host} -> {domain_key}")
            return domain_key
            
        # Remove www. prefix and check again
        if host.startswith('www.'):
            host_without_www = host[4:]
            if host_without_www in self.host_to_domain:
                domain_key = self.host_to_domain[host_without_www]
                logger.debug(f"Host match found after removing www: {host} -> {domain_key}")
                return domain_key
        else:
            # Check if we have www.host registered
            host_with_www = 'www.' + host
            if host_with_www in self.host_to_domain:
                domain_key = self.host_to_domain[host_with_www]
                logger.debug(f"Host match found after adding www: {host} -> {domain_key}")
                return domain_key
        
        # Legacy behavior: Look for direct match in domain keys
        if host in self.domains:
            logger.debug(f"Legacy domain key match found for host: {host}")
            return host
            
        # Fall back to default
        if host != "localhost":
            logger.debug(f"No match found for host: {host}, using default domain")
        return self.default_domain
        
    def get_domain_config(self, domain_key: str) -> DomainConfig:
        """
        Get configuration for a domain.
        
        :param domain_key: Domain key to get config for
        :return: Domain configuration or default if not found
        """
        if domain_key not in self.domains:
            logger.warning(f"Requested domain '{domain_key}' not found, using default")
            return self.domains[self.default_domain]
        return self.domains[domain_key]
        
    def get_theme_config(self, theme_key: str) -> ThemeConfig:
        """
        Get configuration for a theme.
        
        :param theme_key: Theme key to get config for
        :return: Theme configuration or default if not found
        """
        if theme_key not in self.themes:
            logger.warning(f"Requested theme '{theme_key}' not found, using default")
            return self.themes['default']
        return self.themes[theme_key]
        
    def get_allowed_channels(self, domain_key: str) -> Optional[List[str]]:
        """
        Get list of channels allowed on a domain.
        
        :param domain_key: Domain key to check
        :return: List of allowed channels or None if all channels are allowed
        """
        domain = self.get_domain_config(domain_key)
        return domain.channels if not domain.allows_all_channels else None
        
    def is_channel_allowed(self, domain_key: str, channel: str) -> bool:
        """
        Check if a channel is allowed on a domain.
        
        :param domain_key: Domain key to check
        :param channel: Channel name to check
        :return: True if channel is allowed, False otherwise
        """
        domain = self.get_domain_config(domain_key)
        return domain.channel_allowed(channel)
    
    def get_archive_config(self) -> Optional[ArchiveConfig]:
        """
        Get archive configuration.
        
        :return: Archive configuration or None if not loaded
        """
        return self.archive_config

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(constants.CONFIG_DIR) / "domains.toml"

# Global domain manager instance
_domain_manager = None

def init_domain_manager(config_path: Optional[str] = None) -> DomainManager:
    """
    Initialize global domain manager instance.
    
    :param config_path: Path to domain configuration file
    :return: Domain manager instance
    """
    global _domain_manager
    config_path = config_path or DEFAULT_CONFIG_PATH
    logger.info(f"Initializing domain manager with config path: {config_path}")
    _domain_manager = DomainManager(config_path)
    return _domain_manager
    
def get_domain_manager() -> DomainManager:
    """
    Get global domain manager instance.
    
    :return: Domain manager instance
    :raises: RuntimeError if manager not initialized
    """
    global _domain_manager
    if _domain_manager is None:
        logger.info("Domain manager not initialized, initializing with default config")
        _domain_manager = DomainManager(DEFAULT_CONFIG_PATH)
    return _domain_manager