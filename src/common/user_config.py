"""User configuration management for admin access."""

import enum
import json
from pathlib import Path
from typing import Dict, Optional
import tomli

import constants
from common.logging_config import get_logger
logger = get_logger(__name__)

class AdminRole(enum.Enum):
    """Define admin permission levels."""
    SUPER_ADMIN = "super_admin"    # Can manage other admins
    CHANNEL_ADMIN = "channel_admin" # Can grant channel access

class UserConfigManager:
    """Manages user admin configuration."""
    
    def __init__(self, config_path: str):
        """
        Initialize user config manager with configuration file.
        
        :param config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.admin_users: Dict[str, AdminRole] = {}
        self._load_config()
        
    def _load_config(self) -> None:
        """Load and validate admin configuration from TOML file."""
        try:
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)
                admins = {}
                for role, emails in config.get('admins', {}).items():
                    try:
                        admin_role = AdminRole(role)
                        for email in emails:
                            admins[email] = admin_role
                    except ValueError:
                        logger.error(f"Invalid admin role in config: {role}")
                self.admin_users = admins
                        
        except Exception as e:
            logger.error(f"Error loading admin configuration: {str(e)}")
            self.admin_users = {}
    
    def is_admin(self, email: str) -> bool:
        """
        Check if user with given email has admin access.
        
        :param email: User email to check
        :return: True if user is admin, False otherwise
        """
        return email in self.admin_users
    
    def get_admin_role(self, email: str) -> Optional[AdminRole]:
        """
        Get admin role for user with given email.
        
        :param email: User email to check
        :return: AdminRole if user is admin, None otherwise
        """
        return self.admin_users.get(email)
    
    def is_super_admin(self, email: str) -> bool:
        """
        Check if user has super admin privileges.
        
        :param email: User email to check
        :return: True if user is super admin, False otherwise
        """
        return self.get_admin_role(email) == AdminRole.SUPER_ADMIN
    
    def has_channel_admin_access(self, user, channel: str) -> bool:
        """
        Check if user has admin access to a specific channel.
        
        :param user: User object with admin_channel_access field
        :param channel: Channel name to check
        :return: True if user has access, False otherwise
        """
        if not user or not user.admin_channel_access:
            return False
            
        try:
            access = json.loads(user.admin_channel_access)
            return channel in access
        except (json.JSONDecodeError, TypeError):
            return False

# Default configuration file path
DEFAULT_CONFIG_PATH = Path(constants.CONFIG_DIR) / "admin.toml"

# Global user config manager instance
_user_config_manager = None

def init_user_config_manager(config_path: Optional[str] = None) -> UserConfigManager:
    """
    Initialize global user config manager instance.
    
    :param config_path: Path to admin configuration file
    :return: User config manager instance
    """
    global _user_config_manager
    config_path = config_path or DEFAULT_CONFIG_PATH
    _user_config_manager = UserConfigManager(config_path)
    return _user_config_manager
    
def get_user_config_manager() -> UserConfigManager:
    """
    Get global user config manager instance.
    
    :return: User config manager instance
    """
    global _user_config_manager
    if _user_config_manager is None:
        _user_config_manager = UserConfigManager(DEFAULT_CONFIG_PATH)
    return _user_config_manager