"""User-related database functions."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models.database import db
from models.models import User
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.config.user_config import get_user_config_manager

logger = get_logger(__name__)

def is_user_admin(email: str) -> bool:
    """Check if a user is an admin based on their email."""
    if not email:
        return False
    user_config_manager = get_user_config_manager()
    return user_config_manager.is_admin(email)


def get_or_create_user(db_session, request_user) -> User:
    """Get existing user or create new one."""
    db_user = db_session.query(User).options(joinedload('*')).filter_by(email=request_user["email"]).first()
    if not db_user:
        db_user = User(email=request_user["email"], name=request_user["name"])
        db_session.add(db_user)
        db_session.flush()
    return db_user


def get_user_by_id(db_session: Session, user_id: int) -> Optional[User]:
    """
    Get a user by their ID.
    
    :param db_session: SQLAlchemy session
    :param user_id: User ID to look up
    :return: User object if found, None otherwise
    """
    stmt = select(User).where(User.id == user_id)
    return db_session.execute(stmt).scalar_one_or_none()


def get_user_email_domain(user: Optional[User]) -> Optional[str]:
    """
    Extract domain from user's email.
    
    :param user: User session dictionary
    :return: Domain string or None if no email
    """
    if not user or not user.email:
        return None
    return user.email.split('@')[-1]


def check_admin_approval(user_id: int, channel: str) -> bool:
    """
    Check if user has been granted access to admin-controlled channel.
    
    :param user_id: Database ID of user
    :param channel: Channel name to check
    :return: True if user has access, False otherwise
    """
    with db.session() as db_session:
        user = db_session.query(User).get(user_id)
        if not user:
            return False
            
        # Load admin channel access
        access = json.loads(user.admin_channel_access or '{}')
        return channel in access


def check_channel_access(channel: str, user: Optional[User] = None, 
                        ignore_preferences: bool = False) -> bool:
    """
    Check if user has access to the specified channel.
    
    :param channel: Channel name to check access for
    :param user: Optional User model instance
    :param ignore_preferences: If True, only check system restrictions
    :return: True if user can access channel, False otherwise
    """
    if channel is None:
        channel = "private"
        
    channel_manager = get_channel_manager()
    config = channel_manager.get_channel_config(channel)
    if not config:
        logger.error(f"No configuration found for channel {channel}")
        return False

    # First check system access restrictions
    has_admin_access = user and check_admin_approval(user.id, channel)
    system_access = channel_manager.check_system_access(
        channel, 
        email=user.email if user else None,
        has_admin_access=has_admin_access
    )
    
    if not system_access:
        return False
        
    # If ignoring preferences or no user, we're done
    if ignore_preferences or not user:
        return True
        
    # Check user's channel preferences
    try:
        prefs = json.loads(user.channel_preferences or '{}')
        return prefs.get(channel, True)  # Default to enabled if not set
    except json.JSONDecodeError:
        logger.error(f"Invalid channel preferences for user {user.id}")
        return True


def get_user_allowed_channels(user: Optional[User] = None, 
                            ignore_preferences: bool = False) -> List[str]:
    """
    Get list of channels the user can access.
    
    :param user: Optional User model instance
    :param ignore_preferences: If True, only check system restrictions
    :return: List of accessible channel names
    """
    allowed = []
    channel_manager = get_channel_manager()
    for channel in channel_manager.get_channel_names():
        if check_channel_access(channel, user, ignore_preferences):
            allowed.append(channel)
    return allowed


def grant_channel_access_by_id(db_session: Session, user_id: int, channel: str) -> bool:
    """
    Grant channel access to a user by user ID. Returns True if successful.
    
    :param db_session: SQLAlchemy session
    :param user_id: User ID to grant access to
    :param channel: Channel name to grant access to
    :return: True if successful, False otherwise
    """
    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        return False
        
    user = get_user_by_id(db_session, user_id)
    if not user:
        return False
        
    access = json.loads(user.admin_channel_access or '{}')
    access[channel] = datetime.utcnow().isoformat()
    user.admin_channel_access = json.dumps(access)
    
    return True


def revoke_channel_access_by_id(db_session: Session, user_id: int, channel: str) -> bool:
    """
    Revoke channel access from a user by user ID. Returns True if successful.
    
    :param db_session: SQLAlchemy session
    :param user_id: User ID to revoke access from
    :param channel: Channel name to revoke access to
    :return: True if successful, False otherwise
    """
    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        return False
        
    user = get_user_by_id(db_session, user_id)
    if not user:
        return False
        
    access = json.loads(user.admin_channel_access or '{}')
    access.pop(channel, None)
    user.admin_channel_access = json.dumps(access)
    
    return True


def get_user_channel_access_by_id(db_session: Session, user_id: int) -> Dict[str, str]:
    """
    Get all channels a user has access to by user ID and when they were granted.
    
    :param db_session: SQLAlchemy session
    :param user_id: User ID to get access for
    :return: Dictionary of channel names to grant timestamps
    """
    user = get_user_by_id(db_session, user_id)
    if not user:
        return {}
        
    return json.loads(user.admin_channel_access or '{}')


def get_all_users(db_session: Session) -> List[User]:
    """
    Get all users ordered by email.
    
    :param db_session: SQLAlchemy session
    :return: List of User objects ordered by email
    """
    stmt = select(User).order_by(User.email)
    return db_session.execute(stmt).scalars().all()
