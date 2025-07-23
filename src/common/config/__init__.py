"""Common configuration management for Atacama."""

# Channel configuration
from .channel_config import (
    AccessLevel,
    ChannelConfig,
    ChannelManager,
    init_channel_manager,
    get_channel_manager
)

# User configuration
from .user_config import (
    AdminRole,
    UserConfigManager,
    init_user_config_manager,
    get_user_config_manager
)

# Domain configuration
from .domain_config import (
    ThemeConfig,
    DomainConfig,
    DomainManager,
    init_domain_manager,
    get_domain_manager
)

__all__ = [
    # Channel config
    'AccessLevel', 'ChannelConfig', 'ChannelManager', 'init_channel_manager', 'get_channel_manager',
    
    # User config
    'AdminRole', 'UserConfigManager', 'init_user_config_manager', 'get_user_config_manager',
    
    # Domain config
    'ThemeConfig', 'DomainConfig', 'DomainManager', 'init_domain_manager', 'get_domain_manager'
]