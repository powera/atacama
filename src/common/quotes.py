"""
Quote management system for Atacama.

This module handles all quote-related functionality including:
- Extracting quotes from message content
- Storing and retrieving quotes from the database
- Managing quote metadata and relationships
- Quote type validation and processing
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from logging import getLogger

from common.models import Quote, Email, email_quotes

logger = getLogger(__name__)

# Quote types and their descriptions
QUOTE_TYPES = {
    'personal': 'Original quotes from individuals',
    'reference': 'References to existing works',
    'snowclone': 'Variations on known phrases',
    'historical': 'Historical or famous quotes',
    'technical': 'Technical or scientific statements',
}

class QuoteExtractionError(Exception):
    """Raised when quote extraction fails"""
    pass

class QuoteValidationError(Exception):
    """Raised when quote validation fails"""
    pass

def validate_quote(quote_data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate quote data before storage.
    
    Args:
        quote_data: Dictionary containing quote information
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not quote_data.get('text'):
        return False, "Quote text is required"
        
    if len(quote_data['text']) > 1000:
        return False, "Quote text exceeds maximum length of 1000 characters"
        
    quote_type = quote_data.get('quote_type', 'personal')
    if quote_type not in QUOTE_TYPES:
        return False, f"Invalid quote type: {quote_type}"
        
    return True, None

def save_quotes(quotes: List[Dict], message: Email, db_session: Session) -> None:
    """
    Save extracted quotes to database and associate with message.
    
    Args:
        quotes: List of quote dictionaries
        message: Email object to associate quotes with
        db_session: SQLAlchemy session
        
    Raises:
        QuoteValidationError: If quote validation fails
    """
    try:
        for quote_data in quotes:
            # Validate quote data
            is_valid, error = validate_quote(quote_data)
            if not is_valid:
                raise QuoteValidationError(error)
                
            # Check for existing identical quote
            existing_quote = db_session.query(Quote).filter(
                Quote.text == quote_data['text']
            ).first()
            
            if existing_quote:
                message.quotes.append(existing_quote)
                continue
                
            # Create new quote
            quote = Quote(
                text=quote_data['text'],
                quote_type=quote_data.get('quote_type', 'personal'),
                author=quote_data.get('author'),
                source=quote_data.get('source'),
                date=quote_data.get('date'),
                commentary=quote_data.get('commentary')
            )
            
            message.quotes.append(quote)
            db_session.add(quote)
            
    except Exception as e:
        logger.error(f"Failed to save quotes: {str(e)}")
        raise

def get_quotes_by_type(db_session: Session, quote_type: Optional[str] = None) -> List[Quote]:
    """
    Retrieve quotes filtered by type.
    
    Args:
        db_session: SQLAlchemy session
        quote_type: Optional type to filter by
        
    Returns:
        List of Quote objects
    """
    query = db_session.query(Quote)
    
    if quote_type:
        if quote_type not in QUOTE_TYPES:
            raise ValueError(f"Invalid quote type: {quote_type}")
        query = query.filter(Quote.quote_type == quote_type)
        
    return query.order_by(Quote.created_at.desc()).all()

def search_quotes(
    db_session: Session,
    search_term: str,
    quote_type: Optional[str] = None
) -> List[Quote]:
    """
    Search quotes by text content and metadata.
    
    Args:
        db_session: SQLAlchemy session
        search_term: Term to search for
        quote_type: Optional type to filter by
        
    Returns:
        List of matching Quote objects
    """
    query = db_session.query(Quote)
    
    # Build search conditions
    conditions = [
        Quote.text.ilike(f"%{search_term}%"),
        Quote.author.ilike(f"%{search_term}%"),
        Quote.source.ilike(f"%{search_term}%"),
        Quote.commentary.ilike(f"%{search_term}%")
    ]
    
    query = query.filter(or_(*conditions))
    
    if quote_type:
        if quote_type not in QUOTE_TYPES:
            raise ValueError(f"Invalid quote type: {quote_type}")
        query = query.filter(Quote.quote_type == quote_type)
        
    return query.order_by(Quote.created_at.desc()).all()

def update_quote(
    db_session: Session,
    quote_id: int,
    quote_data: Dict
) -> Optional[Quote]:
    """
    Update an existing quote's metadata.
    
    Args:
        db_session: SQLAlchemy session
        quote_id: ID of quote to update
        quote_data: Dictionary of fields to update
        
    Returns:
        Updated Quote object or None if not found
        
    Raises:
        QuoteValidationError: If quote data is invalid
    """
    quote = db_session.query(Quote).get(quote_id)
    if not quote:
        return None
        
    # Validate updated data
    is_valid, error = validate_quote(quote_data)
    if not is_valid:
        raise QuoteValidationError(error)
        
    # Update fields
    quote.text = quote_data.get('text', quote.text)
    quote.quote_type = quote_data.get('quote_type', quote.quote_type)
    quote.author = quote_data.get('author', quote.author)
    quote.source = quote_data.get('source', quote.source)
    quote.date = quote_data.get('date', quote.date)
    quote.commentary = quote_data.get('commentary', quote.commentary)
    
    db_session.commit()
    return quote

def delete_quote(db_session: Session, quote_id: int) -> bool:
    """
    Delete a quote if it exists.
    
    Args:
        db_session: SQLAlchemy session
        quote_id: ID of quote to delete
        
    Returns:
        True if quote was deleted, False if not found
    """
    quote = db_session.query(Quote).get(quote_id)
    if not quote:
        return False
        
    db_session.delete(quote)
    db_session.commit()
    return True
