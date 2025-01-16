"""Channel configuration management for Atacama."""

import os
from pathlib import Path
import enum
import tomli

import constants
from dataclasses import dataclass
from typing import Dict, List, Optional

from common.logging_config import get_logger
logger = get_logger(__name__)

class AccessLevel(enum.Enum):
    """Channel access level enumeration."""
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"

@dataclass
class ChannelConfig:
    """Channel configuration data structure."""
    description: str
    access_level: AccessLevel
    domain_restriction: Optional[str] = None
    requires_preference: bool = False
    requires_admin: bool = False

    @property
    def requires_auth(self) -> bool:
        """Whether the channel requires authentication."""
        return self.access_level in (AccessLevel.PRIVATE, AccessLevel.RESTRICTED)

    @property
    def is_public(self) -> bool:
        """Whether the channel is publicly viewable."""
        return self.access_level == AccessLevel.PUBLIC

class ChannelManager:
    """Manages channel configuration and validation."""
    
    def __init__(self, config_path: str):
        """
        Initialize channel manager with configuration file.
        
        :param config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.channels: Dict[str, ChannelConfig] = {}
        self.default_channel = ""
        self.default_preferences: List[str] = []
        self._load_config()
        
    def _load_config(self) -> None:
        """Load and validate channel configuration from TOML file."""
        try:
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)
                
            # Load channel configurations
            channel_configs = config.get('channels', {})
            for name, settings in channel_configs.items():
                try:
                    access_level = AccessLevel(settings.get('access_level', 'private'))
                except ValueError:
                    logger.error(f"Invalid access_level for channel {name}")
                    raise
                    
                self.channels[name] = ChannelConfig(
                    description=settings.get('description', ''),
                    access_level=access_level,
                    domain_restriction=settings.get('domain_restriction'),
                    requires_preference=settings.get('requires_preference', False)
                    requires_admin=settings.get('requires_admin', False)
                )
                
            # Load defaults
            defaults = config.get('defaults', {})
            self.default_channel = defaults.get('default_channel', 'private')
            self.default_preferences = defaults.get('default_preferences', [])
            
            # Validate configuration
            self._validate_config()
            
        except Exception as e:
            logger.error(f"Error loading channel configuration: {str(e)}")
            raise
            
    def _validate_config(self) -> None:
        """Validate channel configuration for consistency."""
        if not self.channels:
            raise ValueError("No channels defined in configuration")
            
        if self.default_channel not in self.channels:
            raise ValueError(f"Default channel '{self.default_channel}' not found in channel list")
            
        for channel in self.default_preferences:
            if channel not in self.channels:
                raise ValueError(f"Default preference channel '{channel}' not found in channel list")
                
    def get_channel_names(self) -> List[str]:
        """Get list of all channel names."""
        return list(self.channels.keys())
        
    def get_public_channels(self) -> List[str]:
        """Get list of public channel names."""
        return [name for name, config in self.channels.items() 
                if config.is_public]
                
    def get_channel_config(self, channel_name: str) -> Optional[ChannelConfig]:
        """
        Get configuration for specific channel.
        
        :param channel_name: Name of channel to get config for
        :return: Channel configuration or None if not found
        """
        return self.channels.get(channel_name)
        
    def check_channel_access(self, channel_name: str, email: Optional[str] = None) -> bool:
        """
        Check if channel access is allowed.
        
        :param channel_name: Name of channel to check
        :param email: Optional email address for domain restriction checks
        :return: True if access allowed, False otherwise
        """
        config = self.get_channel_config(channel_name)
        if not config:
            return False
            
        if config.is_public:
            return True
            
        if config.access_level == AccessLevel.RESTRICTED:
            if not email:
                return False
            if config.domain_restriction and not email.endswith(config.domain_restriction):
                return False
                
        return True

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(constants.CONFIG_DIR) / "channels.toml"

# Global channel manager instance
_channel_manager = None

def init_channel_manager(config_path: Optional[str] = None) -> ChannelManager:
    """
    Initialize global channel manager instance.
    
    :param config_path: Path to channel configuration file
    :return: Channel manager instance
    """
    global _channel_manager
    config_path = config_path or DEFAULT_CONFIG_PATH
    _channel_manager = ChannelManager(config_path)
    return _channel_manager
    
def get_channel_manager() -> ChannelManager:
    """
    Get global channel manager instance.
    
    :return: Channel manager instance
    :raises: RuntimeError if manager not initialized
    """
    global _channel_manager
    if _channel_manager is None:
        _channel_manager = ChannelManager(DEFAULT_CONFIG_PATH)
    return _channel_manager
