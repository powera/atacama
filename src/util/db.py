from sqlalchemy.orm import Session
from typing import Optional, Tuple
import logging

from sqlalchemy.orm import joinedload
  
from common.config.channel_config import get_channel_manager, AccessLevel
from models.database import db
from models.models import Email, Quote, email_quotes

import aml_parser

logger = logging.getLogger(__name__)

def set_message_parent(child_id: int, parent_id: int) -> Tuple[bool, Optional[str]]:
    """
    Set a parent-child relationship between two messages in the database.
    
    Args:
        child_id: ID of the child message
        parent_id: ID of the parent message
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        
    Example:
        >>> success, error = set_message_parent(5, 3)
        >>> if success:
        ...     print("Relationship established successfully")
        ... else:
        ...     print(f"Error: {error}")
    """
    with db.session() as session:
        try:
            # Get the messages
            child = session.query(Email).get(child_id)
            parent = session.query(Email).get(parent_id)
            
            # Validate messages exist
            if not child:
                return False, f"Child message with ID {child_id} not found"
            if not parent:
                return False, f"Parent message with ID {parent_id} not found"
            
            # Validate channel compatibility
            if child.channel != parent.channel:
                return False, "Parent and child messages must be in the same channel"
                
            # Check for circular references
            current = parent
            while current:
                if current.id == child_id:
                    return False, "Circular reference detected - cannot set parent"
                current = current.parent
            
            # Set the relationship
            child.parent = parent
            
            # Commit happens automatically at the end of the context manager
            logger.info(f"Set message {child_id} as child of {parent_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


def delete_message(message_id: int, cascade: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Delete a message and its associated data from the database.
    
    Args:
        message_id: ID of the message to delete
        cascade: If True, deletes all child messages. If False, reparents child messages
                to the current message's parent
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        
    Example:
        >>> success, error = delete_message(5, cascade=True)
        >>> if success:
        ...     print("Message deleted successfully")
        ... else:
        ...     print(f"Error: {error}")
    """
    with db.session() as session:
        try:
            # Get the message
            message = session.query(Email).get(message_id)
            
            if not message:
                return False, f"Message with ID {message_id} not found"
            
            # Handle child messages based on cascade parameter
            if message.children:
                if cascade:
                    # Log the cascade delete operation
                    child_ids = [child.id for child in message.children]
                    logger.info(f"Cascading delete for message {message_id} will remove children: {child_ids}")
                else:
                    # Reparent children to current message's parent
                    for child in message.children:
                        child.parent = message.parent
                    logger.info(f"Reparenting children of message {message_id} to parent {message.parent_id if message.parent else None}")
            
            # Remove associations with quotes
            # The quotes themselves will be automatically deleted if they're not
            # referenced by other messages due to the relationship configuration
            message.quotes = []
            
            # Delete the message
            session.delete(message)
            
            # Commit happens automatically at the end of the context manager
            logger.info(f"Successfully deleted message {message_id}")
            return True, None
            
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

def reprocess_message(message_id: int):
    """Reprocess an existing message's content."""
    with db.session() as session:
        try:
            message = session.query(Email).options(
                joinedload(Email.quotes)
            ).filter(Email.id == message_id).first()
            
            if not message:
                raise Exception("No message.")
            
            # Remove previous quotes (if otherwise unused).
            existing_quotes = message.quotes[:]  # Make a copy of the list
            message.quotes = []  # Delete quotes
            session.flush()      # Sync removal of relationship

            for quote in existing_quotes:
                # Check if quote is used by other emails
                if not session.query(email_quotes).filter(
                    email_quotes.c.quote_id == quote.id,
                    email_quotes.c.email_id != message_id
                ).first():
                    session.delete(quote)

            message.processed_content = aml_parser.process_message(
                message.content,
                message=message, 
                db_session=session,
            )
            # Process content with access to the message object
            message.preview_content = aml_parser.process_message(
                message.content,
                message=message,
                db_session=session,
                truncated=True
            )
            
            # Commit happens automatically at the end of the context manager
            logger.info(f"Reprocessed message {message_id}")
            
        except Exception as e:
            logger.error(f"Error reprocessing message: {str(e)}")
            return False

def set_message_channel(message_id: int, channel_name: str) -> Tuple[bool, Optional[str]]:
    """
    Set the channel for a message in the database.
    
    Args:
        message_id: ID of the message to update
        channel_name: Name of the channel (must be a valid channel in config)
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        
    Example:
        >>> success, error = set_message_channel(5, "sports")
        >>> if success:
        ...     print("Channel updated successfully")
        ... else:
        ...     print(f"Error: {error}")
    """
    with db.session() as session:
        try:
            # Get the message
            message = session.query(Email).get(message_id)
            
            # Validate message exists
            if not message:
                return False, f"Message with ID {message_id} not found"
                
            # Get channel configuration and validate channel name
            channel_manager = get_channel_manager()
            channel_name = channel_name.lower()
            channel_config = channel_manager.get_channel_config(channel_name)
            
            if not channel_config:
                valid_channels = ", ".join(channel_manager.get_channel_names())
                return False, f"Invalid channel '{channel_name}'. Valid channels are: {valid_channels}"
            
            message.channel = channel_name
            
            # Commit happens automatically at the end of the context manager
            logger.info(f"Set message {message_id} channel to {channel_name}")
            return True, None
            
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


def list_uncategorized_messages() -> list:
    """
    Get all messages that have no channel set.

    Returns:
        List of tuples containing (id, subject) for uncategorized messages

    Example:
        >>> messages = list_uncategorized_messages()
        >>> for id, subject in messages:
        ...     print(f"Message {id}: {subject}")
    """
    with db.session() as session:
        try:
            messages = session.query(Email.id, Email.subject)\
                .filter(Email.channel == None)\
                .all()
            return messages

        except Exception as e:
            logger.error(f"Error listing uncategorized messages: {str(e)}")
            return []
