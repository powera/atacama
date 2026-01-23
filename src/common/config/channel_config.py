"""Channel configuration management for Atacama."""

from pathlib import Path
import enum
import tomli

import constants
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Union

from common.base.logging_config import get_logger
logger = get_logger(__name__)

class AccessLevel(enum.Enum):
    """Channel access level enumeration."""
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"

@dataclass
class ChannelConfig:
    """Channel configuration data structure."""
    name: str
    description: str
    access_level: AccessLevel
    group: str = "General"  # Default group for backwards compatibility
    domain_restriction: Optional[str] = None
    requires_admin: bool = False
    display_name: Optional[str] = None

    @property
    def requires_auth(self) -> bool:
        """Whether the channel requires authentication."""
        return self.access_level in (AccessLevel.PRIVATE, AccessLevel.RESTRICTED)

    @property
    def is_public(self) -> bool:
        """Whether the channel is publicly viewable."""
        return self.access_level == AccessLevel.PUBLIC

    def get_display_name(self) -> str:
        """
        Get the display name for this channel.

        :return: The configured display name or title-cased channel name
        """
        return self.display_name or self.name.title()

class ChannelManager:
    """Manages channel configuration and validation."""
    
    def __init__(self, config_path: Union[str, Path]):
        """
        Initialize channel manager with configuration file.

        :param config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.channels: Dict[str, ChannelConfig] = {}
        self.valid_groups: List[str] = []
        self.default_channel = ""
        self.default_preferences: List[str] = []
        self._load_config()
        
    def _load_config(self) -> None:
        """Load and validate channel configuration from TOML file."""
        try:
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)
            
            # Load valid groups first
            groups_config = config.get('groups', {})
            self.valid_groups = groups_config.get('valid_groups', ['General'])
            if 'General' not in self.valid_groups:
                self.valid_groups.append('General')  # Ensure General is always valid
                
            # Load channel configurations
            channel_configs = config.get('channels', {})
            for name, settings in channel_configs.items():
                try:
                    access_level = AccessLevel(settings.get('access_level', 'private'))
                except ValueError:
                    logger.error(f"Invalid access_level for channel {name}")
                    raise
                
                # Validate group
                group = settings.get('group', 'General')
                if group not in self.valid_groups:
                    raise ValueError(f"Invalid group '{group}' for channel '{name}'. Valid groups are: {', '.join(self.valid_groups)}")
                    
                self.channels[name] = ChannelConfig(
                    name=name,
                    description=settings.get('description', ''),
                    access_level=access_level,
                    group=group,
                    domain_restriction=settings.get('domain_restriction'),
                    requires_admin=settings.get('requires_admin', False),
                    display_name=settings.get('display_name', None)
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

    def get_channel_groups(self) -> Dict[str, List[str]]:
        """
        Get channels organized by group, maintaining group order from config.
        
        :return: Dictionary mapping group names to lists of channel names, 
                ordered according to valid_groups
        """
        groups: Dict[str, List[str]] = {group: [] for group in self.valid_groups}
        for name, config in self.channels.items():
            groups[config.group].append(name)
        
        # Sort channels within each group
        return {group: sorted(channels) for group, channels in groups.items() if channels}
                
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
        
    def get_display_name(self, channel_name: str) -> str:
        """
        Get the display name for a channel.
        
        :param channel_name: The channel name
        :return: The configured display name or title-cased channel name
        """
        config = self.get_channel_config(channel_name)
        if config:
            return config.get_display_name()
        return channel_name.title()

    def check_system_access(self, channel_name: str, email: Optional[str] = None, 
                         has_admin_access: bool = False) -> bool:
        """
        Check if channel access is allowed by system restrictions (ignoring user preferences).
        
        :param channel_name: Name of channel to check
        :param email: Optional email address for domain restriction checks
        :param has_admin_access: Whether user has admin access to restricted channels
        :return: True if access allowed, False otherwise
        """
        config = self.get_channel_config(channel_name)
        if not config:
            return False
            
        if config.is_public:
            return True
            
        # Private channels just need authentication
        if config.access_level == AccessLevel.PRIVATE:
            return email is not None
            
        # Restricted channels need domain and/or admin checks
        if config.access_level == AccessLevel.RESTRICTED:
            if not email:
                return False
                
            # Check domain restriction if it exists
            if config.domain_restriction:
                if not email.endswith(config.domain_restriction):
                    return False
                    
            # Check admin restriction if it exists
            if config.requires_admin and not has_admin_access:
                return False
                
        return True

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(constants.CONFIG_DIR) / "channels.toml"

# Global channel manager instance
_channel_manager = None

def init_channel_manager(config_path: Optional[Union[str, Path]] = None) -> ChannelManager:
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
