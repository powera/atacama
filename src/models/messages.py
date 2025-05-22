"""Database functions for retrieving messages and message chains with configurable access control."""

import json
from flask import session, g
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from models.database import db
from models import Email, User
from common.config.channel_config import get_channel_manager, AccessLevel
from common.base.logging_config import get_logger
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


def check_message_access(message: Email, ignore_preferences: bool = True) -> bool:
    """
    Check if current user can access the message.
    By default, ignores user preferences for direct message access.
    
    :param message: Email object to check access for
    :param ignore_preferences: If True, only check system restrictions
    :return: True if user can access message, False otherwise
    """
    return check_channel_access(message.channel, g.user, ignore_preferences)


def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Retrieve a message by ID with all relevant relationships.
    
    :param message_id: ID of the message to retrieve
    :return: Email object if found and accessible, None otherwise
    """
    with db.session() as db_session:
        db_session.expire_on_commit = False  # Keep object usable after commit
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message or not check_message_access(message, ignore_preferences=True):
            return None
            
        return message


def get_message_chain(message_id: int) -> List[Email]:
    """
    Retrieve the full chain of messages related to a given message ID.
    
    :param message_id: ID of the message to get chain for
    :return: List of accessible Email objects in chronological order
    """
    with db.session() as db_session:
        db_session.expire_on_commit = False
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message or not check_message_access(message, ignore_preferences=True):
            return []
            
        chain = []
        
        # Add parent chain
        current = message
        while current.parent:
            if check_message_access(current.parent, ignore_preferences=True):
                chain.insert(0, current.parent)
            current = current.parent
            
        # Add target message
        chain.append(message)
        
        # Add accessible children
        matching_children = [
            child for child in message.children 
            if child.channel == message.channel and 
               check_message_access(child, ignore_preferences=True)
        ]
        chain.extend(sorted(matching_children, key=lambda x: x.created_at))

        # Refresh for good luck
        for msg in chain:
            db_session.refresh(msg)
       
        return chain


def get_filtered_messages(
    db_session,
    older_than_id: Optional[int] = None,
    older_than_timestamp: Optional[datetime] = None,
    user_id: Optional[int] = None,
    channel: Optional[str] = None,
    allowed_channels: Optional[List[str]] = None,
    limit: int = 10
) -> Tuple[List[Email], bool]:
    """
    Retrieve messages with filtering and pagination.
    Respects user preferences and domain restrictions for stream views.
    
    Either older_than_id or older_than_timestamp can be specified, but not both.
    If neither is specified, the most recent messages are returned.

    :param db_session: Database session
    :param older_than_id: Get messages older than this ID
    :param older_than_timestamp: Get messages older than this timestamp
    :param user_id: Filter by author user ID
    :param channel: Filter by channel name
    :param allowed_channels: Explicit list of allowed channels (overrides automatic calculation)
    :param limit: Maximum messages to return
    :return: Tuple of (messages, has_more)
    """
    if older_than_id is not None and older_than_timestamp is not None:
        raise ValueError("Cannot specify both older_than_id and older_than_timestamp")
        
    query = db_session.query(Email).options(
        joinedload(Email.quotes),
        joinedload(Email.author)
    )

    if older_than_id is not None:
        query = query.filter(Email.id < older_than_id)
    elif older_than_timestamp is not None:
        query = query.filter(Email.created_at < older_than_timestamp)

    if user_id:
        query = query.filter(Email.author_id == user_id)

    if channel:
        channel = channel.lower()
        if not get_channel_manager().get_channel_config(channel):
            logger.error(f"Invalid channel specified: {channel}")
            return [], False
            
        query = query.filter(Email.channel == channel)
        
        if not check_channel_access(channel, g.user, ignore_preferences=False):
            logger.warning(f"User lacks access to channel: {channel}")
            return [], False
    else:
        # Use provided allowed_channels if specified, otherwise calculate them
        if allowed_channels is None:
            allowed_channels = get_user_allowed_channels(g.user, ignore_preferences=False)
        query = query.filter(Email.channel.in_(allowed_channels))

    if older_than_id is not None:
        # Get one extra to check if there are more
        messages = query.order_by(Email.id.desc()).limit(limit + 1).all()
    else:
        # Get one extra to check if there are more
        messages = query.order_by(Email.created_at.desc()).limit(limit + 1).all()

    has_more = len(messages) > limit
    messages = messages[:limit]

    # Format timestamps
    for message in messages:
        message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

    return messages, has_more


def get_domain_filtered_messages(
    db_session,
    older_than_id: Optional[int] = None,
    older_than_timestamp: Optional[datetime] = None,
    user_id: Optional[int] = None,
    channel: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 10
) -> Tuple[List[Email], bool]:
    """
    Retrieve messages with filtering and pagination, including domain restrictions.
    This properly filters channels at the database query level for efficiency.
    
    :param db_session: Database session
    :param older_than_id: Get messages older than this ID
    :param older_than_timestamp: Get messages older than this timestamp
    :param user_id: Filter by author user ID
    :param channel: Filter by channel name
    :param domain: Current domain for channel filtering
    :param limit: Maximum messages to return
    :return: Tuple of (messages, has_more)
    """
    from common.config.domain_config import get_domain_manager
    
    # Get user-allowed channels first
    user_allowed_channels = get_user_allowed_channels(g.user, ignore_preferences=False)
    
    # Apply domain filtering if necessary
    if domain and not channel:
        domain_manager = get_domain_manager()
        domain_config = domain_manager.get_domain_config(domain)
        
        if not domain_config.allows_all_channels:
            # Filter to only domain-allowed channels
            domain_filtered_channels = []
            for ch in user_allowed_channels:
                if domain_manager.is_channel_allowed(domain, ch):
                    domain_filtered_channels.append(ch)
            user_allowed_channels = domain_filtered_channels
    
    # Now get messages with the properly filtered channel list
    return get_filtered_messages(
        db_session,
        older_than_id=older_than_id,
        older_than_timestamp=older_than_timestamp,
        user_id=user_id,
        channel=channel,
        allowed_channels=user_allowed_channels,
        limit=limit
    )