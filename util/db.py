from sqlalchemy.orm import Session
from common.models import Email, Quote
from typing import Optional, Tuple
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
    
logger = logging.getLogger(__name__)

def set_message_parent(child_id: int, parent_id: int, db_url: str = 'sqlite:///emails.db') -> Tuple[bool, Optional[str]]:
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


def delete_message(message_id: int, db_url: str = 'sqlite:///emails.db', cascade: bool = False) -> Tuple[bool, Optional[str]]:
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
