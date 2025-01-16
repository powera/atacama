"""Database functions for retrieving messages and message chains with configurable access control."""

from flask import session, g
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import json
import enum
from functools import lru_cache

from common.database import db

from common.models import Email, Channel, User
from common.logging_config import get_logger
logger = get_logger(__name__)

class AccessStrategy(enum.Enum):
    """Define how access control is handled for each channel."""
    PUBLIC = "public"           # Anyone can view
    PRIVATE = "private"        # Must be logged in
    DOMAIN = "domain"          # Must have specific email domain
    ADMIN = "admin"           # Must be explicitly granted access
    
# Define access control configuration for each channel
CHANNEL_ACCESS = {
    Channel.PRIVATE: AccessStrategy.PRIVATE,
    Channel.POLITICS: AccessStrategy.DOMAIN,
    Channel.ORINOCO: AccessStrategy.ADMIN,
    # All other channels default to PUBLIC
}

# Define domain restrictions for DOMAIN strategy channels
DOMAIN_RESTRICTIONS = {
    Channel.POLITICS: ["earlyversion.com"]
}

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
def check_admin_approval(user_id: int, channel: Channel) -> bool:
    """
    Check if user has been granted access to admin-controlled channel.
    
    :param user_id: Database ID of user
    :param channel: Channel to check
    :return: True if user has access, False otherwise
    """
    with db.session() as db_session:
        user = db_session.query(User).get(user_id)
        if not user:
            return False
            
        # Load channel preferences
        prefs = json.loads(user.channel_preferences or '{}')
        return prefs.get(f"admin_{channel.value}", False)


def check_channel_access(channel: Channel, user: Optional[User] = None) -> bool:
    """
    Check if current user has access to the specified channel.
    
    :param channel: Channel to check access for
    :param user: Optional common.models.User
    :return: True if user can access channel, False otherwise
    """
    # Get access strategy for channel
    strategy = CHANNEL_ACCESS.get(channel, AccessStrategy.PUBLIC)
    
    # Handle each access strategy
    if strategy == AccessStrategy.PUBLIC:
        return True
        
    if strategy == AccessStrategy.PRIVATE:
        return user is not None
        
    if strategy == AccessStrategy.DOMAIN:
        if not user:
            return False
        user_domain = get_user_email_domain(user)
        allowed_domains = DOMAIN_RESTRICTIONS.get(channel, [])
        return user_domain in allowed_domains
        
    if strategy == AccessStrategy.ADMIN:
        if not user:
            return False
        db_user = g.get('user')
        if not db_user:
            return False
        return check_admin_approval(db_user.id, channel)
        
    logger.error(f"Unknown access strategy {strategy} for channel {channel}")
    return False

def get_user_allowed_channels(user: Optional[User] = None) -> List[Channel]:
    """
    Get list of channels the user can access.
    
    :param user: Optional user session dictionary
    :return: List of accessible Channel enums
    """
    allowed = []
    for channel in Channel:
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
        try:
            channel_enum = Channel[channel.upper()]
            query = query.filter(Email.channel == channel_enum)
            
            if not check_channel_access(channel_enum, g.user):
                logger.warning(f"User lacks access to channel: {channel}")
                return [], False
                
        except KeyError:
            logger.error(f"Invalid channel specified: {channel}")
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
