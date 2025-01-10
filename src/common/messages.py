"""Database functions for retrieving messages and message chains."""
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from common.database import setup_database
Session, db_success = setup_database()

from common.models import Email, Channel

from common.logging_config import get_logger
logger = get_logger(__name__)


def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Helper function to retrieve a message by ID with all relevant relationships.
    
    Args:
        message_id: ID of the message to retrieve
        
    Returns:
        Email object if found, None otherwise
    """
    db_session = Session()
    try:
        return db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
    except Exception as e:
        logger.error(f"Error retrieving message {message_id}: {str(e)}")
        return None
    finally:
        db_session.close()


def get_message_chain(message_id: int) -> List[Email]:
    """
    Retrieve the full chain of messages related to a given message ID.
    Includes the parent chain and all child messages.
    
    Args:
        message_id: ID of the message to get the chain for
        
    Returns:
        List of Email objects representing the chain, ordered chronologically
    """
    db_session = Session()
    try:
        # Get the target message with its relationships
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message:
            return []
            
        # Build the chain
        chain = []
        
        # Add parent chain in reverse chronological order
        current = message
        while current.parent:
            chain.insert(0, current.parent)
            current = current.parent
            
        # Add the target message
        chain.append(message)
        
        # Add children in chronological order that match the channel
        matching_children = [child for child in message.children if child.channel == message.channel]
        chain.extend(sorted(matching_children, key=lambda x: x.created_at))
        
        return chain
        
    except Exception as e:
        logger.error(f"Error retrieving message chain for {message_id}: {str(e)}")
        return []
    finally:
        db_session.close()


def get_filtered_messages(db_session, older_than_id=None, user_id=None, channel=None, limit=10):
    """
    Retrieve messages with optional filtering and pagination.

    :param db_session: Database session
    :param older_than_id: If provided, get messages older than this ID
    :param user_id: If provided, filter messages by user ID
    :param channel: If provided, filter messages by channel/topic
    :param limit: Maximum number of messages to return
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
        except KeyError:
            logger.error(f"Invalid channel specified: {channel}")
            return [], False

    # Get one extra message to check if there are more
    messages = query.order_by(Email.id.desc()).limit(limit + 1).all()

    has_more = len(messages) > limit
    messages = messages[:limit]  # Remove the extra message if it exists

    # Format timestamps
    for message in messages:
        message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

    return messages, has_more
