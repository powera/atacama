from sqlalchemy.orm import Session
from typing import Optional, Tuple
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, sessionmaker
  
from constants import DB_PATH
from common.models import Email, Channel, Quote, email_quotes
from common.colorscheme import ColorScheme
color_processor = ColorScheme()

logger = logging.getLogger(__name__)

def set_message_parent(child_id: int, parent_id: int, db_url: str = f'sqlite:///{DB_PATH}') -> Tuple[bool, Optional[str]]:
    """
    Set a parent-child relationship between two messages in the database.
    
    Args:
        child_id: ID of the child message
        parent_id: ID of the parent message
        db_url: SQLAlchemy database URL (defaults to SQLite)
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        
    Example:
        >>> success, error = set_message_parent(5, 3)
        >>> if success:
        ...     print("Relationship established successfully")
        ... else:
        ...     print(f"Error: {error}")
    """
    try:
        # Create database engine and session
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            # Get the messages
            child = session.query(Email).get(child_id)
            parent = session.query(Email).get(parent_id)
            
            # Validate messages exist
            if not child:
                return False, f"Child message with ID {child_id} not found"
            if not parent:
                return False, f"Parent message with ID {parent_id} not found"
                
            # Check for circular references
            current = parent
            while current:
                if current.id == child_id:
                    return False, "Circular reference detected - cannot set parent"
                current = current.parent
            
            # Set the relationship
            child.parent = parent
            
            # Commit the changes
            session.commit()
            
            logger.info(f"Set message {child_id} as child of {parent_id}")
            return True, None
            
        except Exception as e:
            session.rollback()
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        finally:
            session.close()
            
    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def delete_message(message_id: int, db_url: str = f'sqlite:///{DB_PATH}', cascade: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Delete a message and its associated data from the database.
    
    Args:
        message_id: ID of the message to delete
        db_url: SQLAlchemy database URL (defaults to SQLite)
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
    try:
        # Create database engine and session
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
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
            session.commit()
            
            logger.info(f"Successfully deleted message {message_id}")
            return True, None
            
        except Exception as e:
            session.rollback()
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        finally:
            session.close()
            
    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def reprocess_message(message_id: int):
    """Reprocess an existing message's content."""
    try:
        engine = create_engine(f'sqlite:///{DB_PATH}')
        SessionLocal = sessionmaker(bind=engine)
        db_session = SessionLocal()
        message = db_session.query(Email).options(
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message:
            raise Exception("No message.")
        
        # Remove previous quotes (if otherwise unused).
        existing_quotes = message.quotes[:]  # Make a copy of the list
        message.quotes = []  # Delete quotes
        db_session.flush()      # Sync removal of relationship

        for quote in existing_quotes:
            # Check if quote is used by other emails
            if not db_session.query(email_quotes).filter(
                email_quotes.c.quote_id == quote.id,
                email_quotes.c.email_id != message_id
            ).first():
                db_session.delete(quote)

        message.processed_content = color_processor.process_content(
            message.content,
            message=message,
            db_session=db_session,
        )
        
        db_session.commit()
        
        logger.info(f"Reprocessed message {message_id}")
        
    except Exception as e:
        logger.error(f"Error reprocessing message: {str(e)}")
        return False
        
    finally:
        db_session.close()

def set_message_channel(message_id: int, channel_name: str, db_url: str = f'sqlite:///{DB_PATH}') -> Tuple[bool, Optional[str]]:
    """
    Set the channel for a message in the database.
    
    Args:
        message_id: ID of the message to update
        channel_name: Name of the channel (must match Channel enum values)
        db_url: SQLAlchemy database URL (defaults to SQLite)
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        
    Example:
        >>> success, error = set_message_channel(5, "SPORTS")
        >>> if success:
        ...     print("Channel updated successfully")
        ... else:
        ...     print(f"Error: {error}")
    """
    try:
        # Create database engine and session
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            # Get the message
            message = session.query(Email).get(message_id)
            
            # Validate message exists
            if not message:
                return False, f"Message with ID {message_id} not found"
                
            # Validate and set channel
            try:
                channel = Channel[channel_name.upper()]
                message.channel = channel
            except KeyError:
                valid_channels = ", ".join([c.name for c in Channel])
                return False, f"Invalid channel '{channel_name}'. Valid channels are: {valid_channels}"
            
            # Commit the changes
            session.commit()
            
            logger.info(f"Set message {message_id} channel to {channel.name}")
            return True, None
            
        except Exception as e:
            session.rollback()
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        finally:
            session.close()
            
    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
