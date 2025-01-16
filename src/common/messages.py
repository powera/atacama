"""Database functions for retrieving messages and message chains with configurable access control."""

from flask import session, g
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import json
from functools import lru_cache

from common.database import db
from common.models import Email, User
from common.channel_config import get_channel_manager, AccessLevel
from common.logging_config import get_logger
logger = get_logger(__name__)


def get_user_email_domain(user: Optional[User]) -> Optional[str]:
    """
    Extract domain from user's email.
    
    :param user: User session dictionary
    :return: Domain string or None if no email
    """
    if not user or not user.email:
        return None
    return user.email.split('@')[-1]


@lru_cache(maxsize=1000)
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
            
        # Load channel preferences
        access = json.loads(user.admin_channel_access or '{}')
        return channel in access


def check_channel_access(channel: str, user: Optional[User] = None) -> bool:
    """
    Check if current user has access to the specified channel.
    
    :param channel: Channel name to check access for
    :param user: Optional common.models.User
    :return: True if user can access channel, False otherwise
    """
    if channel is None:  # legacy
        channel = "private"
    channel = channel
    channel_manager = get_channel_manager()
    config = channel_manager.get_channel_config(channel)
    if not config:
        logger.error(f"No configuration found for channel {channel}")
        return False

    # Public channels are always accessible
    if config.access_level == AccessLevel.PUBLIC:
        return True

    # Private and restricted channels require authentication
    if not user:
        return False

    # For restricted channels, check domain restrictions
    if config.access_level == AccessLevel.RESTRICTED:
        if config.domain_restriction:
            user_domain = get_user_email_domain(user)
            if not user_domain or not user_domain.endswith(config.domain_restriction):
                return False

        # Check if channel requires preference to be enabled
        if config.requires_preference:
            db_user = g.get('user')
            if not db_user:
                return False
            prefs = json.loads(db_user.channel_preferences or '{}')
            if not prefs.get(channel, False):
                return False

    return True


def get_user_allowed_channels(user: Optional[User] = None) -> List[str]:
    """
    Get list of channels the user can access.
    
    :param user: Optional user session dictionary
    :return: List of accessible channel names
    """
    allowed = []
    channel_manager = get_channel_manager()
    for channel in channel_manager.get_channel_names():
        if check_channel_access(channel, user):
            allowed.append(channel)
    return allowed


def check_message_access(message: Email) -> bool:
    """
    Check if current user has access to view the message.
    
    :param message: Email object to check access for
    :return: True if user can access message, False otherwise
    """
    user = session.get('user')
    return check_channel_access(message.channel, user)


def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Retrieve a message by ID with all relevant relationships.
    
    :param message_id: ID of the message to retrieve
    :return: Email object if found and accessible, None otherwise
    """
    with db.session() as db_session:
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message or not check_message_access(message):
            return None
            
        return message


def get_message_chain(message_id: int) -> List[Email]:
    """
    Retrieve the full chain of messages related to a given message ID.
    
    :param message_id: ID of the message to get chain for
    :return: List of accessible Email objects in chronological order
    """
    with db.session() as db_session:
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message or not check_message_access(message):
            return []
            
        chain = []
        
        # Add parent chain
        current = message
        while current.parent:
            if check_message_access(current.parent):
                chain.insert(0, current.parent)
            current = current.parent
            
        # Add target message
        chain.append(message)
        
        # Add accessible children
        matching_children = [
            child for child in message.children 
            if child.channel == message.channel and check_message_access(child)
        ]
        chain.extend(sorted(matching_children, key=lambda x: x.created_at))
        
        return chain


def get_filtered_messages(
    db_session,
    older_than_id: Optional[int] = None,
    user_id: Optional[int] = None,
    channel: Optional[str] = None,
    limit: int = 10
) -> Tuple[List[Email], bool]:
    """
    Retrieve messages with filtering and pagination.
    
    :param db_session: Database session
    :param older_than_id: Get messages older than this ID
    :param user_id: Filter by author user ID
    :param channel: Filter by channel name
    :param limit: Maximum messages to return
    :return: Tuple of (messages, has_more)
    """
    query = db_session.query(Email).options(
        joinedload(Email.quotes),
        joinedload(Email.author)
    )

    if older_than_id:
        query = query.filter(Email.id < older_than_id)

    if user_id:
        query = query.filter(Email.author_id == user_id)

    if channel:
        channel = channel.lower()
        if not get_channel_manager().get_channel_config(channel):
            logger.error(f"Invalid channel specified: {channel}")
            return [], False
            
        query = query.filter(Email.channel == channel)
        
        if not check_channel_access(channel, g.user):
            logger.warning(f"User lacks access to channel: {channel}")
            return [], False
    else:
        # Filter to allowed channels
        allowed_channels = get_user_allowed_channels(g.user)
        query = query.filter(Email.channel.in_(allowed_channels))

    # Get one extra to check if there are more
    messages = query.order_by(Email.id.desc()).limit(limit + 1).all()

    has_more = len(messages) > limit
    messages = messages[:limit]

    # Format timestamps
    for message in messages:
        message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

    return messages, has_more
