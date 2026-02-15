"""
Quote management system for Atacama.

This module handles all quote-related functionality including:
- Extracting quotes from message content
- Storing and retrieving quotes from the database
- Managing quote metadata and relationships
- Quote type validation and processing
"""

from typing import List, Dict, Optional, Tuple, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from logging import getLogger

from common.llm.openai_client import DEFAULT_MODEL, generate_chat
from common.llm.telemetry import LLMUsage
from common.llm.types import Schema, SchemaProperty
from models.models import Email, Quote

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

class LLMUncertainError(Exception):
    """Raised when the LLM is not confident enough in its analysis"""
    def __init__(self, confidence: float, message: str = "LLM confidence too low"):
        self.confidence = confidence
        self.message = f"{message} (confidence: {confidence:.1%})"
        super().__init__(self.message)

def _create_quote_metadata_schema() -> Schema:
    """Create the schema for quote metadata."""
    return Schema(
        "QuoteMetadata",
        "Metadata about a quote including analysis and attribution",
        {
            "theme": SchemaProperty("string", "The main theme or topic (e.g. 'love', 'persistence', 'technology')"),
            "tone": SchemaProperty("string", "The emotional tone (e.g. 'inspirational', 'humorous', 'critical')"),
            "attribution": SchemaProperty(
                "object",
                "Information about the quote's origin",
                properties={
                    "author_type": SchemaProperty("string", "Type of author", enum=["historical", "fictional"]),
                    "speaker": SchemaProperty("string", "The character/person who speaks the quote"),
                    "context": SchemaProperty("string", "Publication/work where quote appears, or historical context"),
                    "time_period": SchemaProperty("string", "Historical or fictional time period of the quote")
                }
            ),
            "interpretation": SchemaProperty("string", "A brief interpretation of the quote's meaning"),
            "keywords": SchemaProperty("array", "Relevant keywords", items={"type": "string"}),
            "related_topics": SchemaProperty("array", "Related topics or themes", items={"type": "string"}),
            "literary_devices": SchemaProperty("array", "Notable literary devices used", items={"type": "string"})
        }
    )

def _create_quote_details_schema() -> Schema:
    """Create the schema for quote details extraction."""
    return Schema(
        "QuoteDetails",
        "Detailed information about a quote's origin and type",
        {
            "original_author": SchemaProperty("string", "The original author of the quote"),
            "source": SchemaProperty("string", "The source of the quote (book, speech, etc.)"),
            "date": SchemaProperty("string", "When the quote was originally made (approximate if unknown)"),
            "quote_type": SchemaProperty("string", "Type of quote", enum=list(QUOTE_TYPES.keys())),
            "confidence": SchemaProperty("number", "Confidence score (0-1) of the extraction")
        }
    )

def generate_quote_metadata(
    quote_text: str,
    model: str = DEFAULT_MODEL
) -> Tuple[Dict[str, Any], LLMUsage]:
    """
    Generate metadata about a quote using the ChatGPT API.
    
    Args:
        quote_text: The text of the quote to analyze
        model: The model to use for generation
        
    Returns:
        Tuple of (metadata dict, LLM usage stats)
    """
    schema = _create_quote_metadata_schema()
    
    prompt = f"""Analyze this quote and provide metadata in the requested format.
    
Quote: "{quote_text}"

For fictional works, distinguish between the actual author and any fictional speakers."""

    response = generate_chat(
        prompt=prompt,
        model=model,
        json_schema=schema,
        context="You are a literary analysis expert. Provide detailed and accurate metadata about the given quote."
    )
    
    return response.structured_data, response.usage


def extract_quote_details(
    quote_text: str,
    commentary: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    return_full_response: bool = False
) -> Union[Dict[str, Any], Any]:
    """
    Extract detailed information about a quote including author, source, and type.

    Args:
        quote_text: The text of the quote to analyze
        commentary: Optional additional context or commentary about the quote
        model: The model to use for generation
        return_full_response: If True, returns the full response object instead of just structured data

    Returns:
        Dictionary containing the extracted quote details or the full response object
    """
    schema = _create_quote_details_schema()

    prompt = f"""Extract detailed information about this quote:

Quote: "{quote_text}"""

    if commentary:
        prompt += f"\n\nCommentary: {commentary}"

    prompt += "\n\nProvide the most likely original author, source, date, and quote type."

    response = generate_chat(
        prompt=prompt,
        model=model,
        json_schema=schema,
        context="""You are an expert in quotes and their origins.
        Extract accurate information about the quote's source and type.
        If you're not certain about a field, make an educated guess or leave it empty."""
    )

    return response if return_full_response else response.structured_data


def enrich_quote_with_llm(
    db_session: Session,
    quote_id: int,
    model: str = DEFAULT_MODEL,
    min_confidence: float = 0.75
) -> Quote:
    """
    Enrich a quote with LLM-extracted metadata and update the database.
    
    Args:
        db_session: Database session
        quote_id: ID of the quote to enrich
        model: The model to use for generation
        min_confidence: Minimum confidence threshold (0-1) to accept the LLM's analysis
        
    Returns:
        The updated Quote object
        
    Raises:
        ValueError: If quote is not found
        LLMUncertainError: If confidence is below min_confidence
        Exception: For any other errors during processing
    """
    # Get the quote from database
    quote = db_session.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote with ID {quote_id} not found")
    
    try:
        # Extract details using LLM
        response = extract_quote_details(
            quote_text=quote.text,
            commentary=quote.commentary,
            model=model,
            return_full_response=True
        )
        
        # Get the structured data from the response
        details = response.structured_data if hasattr(response, 'structured_data') else response
        
        # Check confidence level
        confidence = details.get('confidence', 0)
        if confidence < min_confidence:
            # Log the LLM response when confidence is too low
            logger.warning(
                f"LLM response for quote {quote_id} had low confidence ({confidence:.1%}): "
                f"Original author: {details.get('original_author', 'N/A')}, "
                f"Source: {details.get('source', 'N/A')}, "
                f"Date: {details.get('date', 'N/A')}, "
                f"Quote type: {details.get('quote_type', 'N/A')}"
            )
            
            # If there's additional thought from the LLM, log that too
            if hasattr(response, 'additional_thought') and response.additional_thought:
                logger.warning(f"LLM additional thought: {response.additional_thought}")
                
            raise LLMUncertainError(
                confidence=confidence,
                message=f"LLM confidence too low for quote {quote_id}"
            )
        
        # Update quote with extracted details
        if details.get('original_author'):
            quote.original_author = details['original_author']
        if details.get('source'):
            quote.source = details['source']
        if details.get('date'):
            quote.date = details['date']
        if details.get('quote_type'):
            quote.quote_type = details['quote_type']
        
        # Add confidence to commentary if it doesn't already mention it
        if 'confidence:' not in (quote.commentary or '').lower():
            confidence_comment = f"\n\n[Extracted with {confidence:.1%} confidence]"
            quote.commentary = f"{quote.commentary or ''}{confidence_comment}"
        
        db_session.commit()
        logger.info(f"Successfully enriched quote {quote_id} with LLM data (confidence: {confidence:.1%})")
        return quote
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to enrich quote {quote_id} with LLM: {str(e)}")
        if not isinstance(e, (ValueError, LLMUncertainError)):
            # Log the full error for debugging, but don't expose internal details
            logger.exception(f"Unexpected error enriching quote {quote_id}")
            raise Exception(f"Failed to process quote: {str(e)}") from e
        raise


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
    
    # Validate date format if present
    if 'date' in quote_data and quote_data['date']:
        try:
            if not isinstance(quote_data['date'], (str, datetime)):
                return False, "Date must be a string or datetime object"
            if isinstance(quote_data['date'], str):
                datetime.strptime(quote_data['date'], '%Y-%m-%d')
        except ValueError:
            return False, "Date must be in YYYY-MM-DD format or a datetime object"
        
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
                original_author=quote_data.get('original_author'),
                source=quote_data.get('source'),
                date=quote_data.get('date'),
                commentary=quote_data.get('commentary'),
                author=message.author,
                channel=message.channel
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
        Quote.original_author.ilike(f"%{search_term}%"),
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
    quote.original_author = quote_data.get('original_author', quote.original_author)
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
