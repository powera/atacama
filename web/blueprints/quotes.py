from flask import Blueprint, request, render_template, url_for, redirect
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload
import logging
from typing import Dict, Any, Optional, List, Tuple

from common.database import setup_database
Session, db_success = setup_database()

from common.models import Email, Quote, email_quotes
from common.colorscheme import ColorScheme
from .auth import require_auth

quotes_bp = Blueprint('quotes', __name__)

QUOTE_TYPES = ['yellow-quote', 'yellow-snowclone', 'blue-quote']
def extract_quotes(content: str) -> List[Dict[str, str]]:
    """
    Extract quotes from content using yellow and blue color tags.
    
    :param content: Message content
    :return: List of extracted quotes with metadata
    """
    quotes = []
    # Extract yellow-tagged quotes
    yellow_quotes = color_processor.extract_color_content(content, 'yellow')
    for quote in yellow_quotes:
        quotes.append({
            'text': quote,
            'quote_type': 'yellow-quote'
        })
    
    # Extract blue-tagged aphorisms
    blue_quotes = color_processor.extract_color_content(content, 'blue')
    for quote in blue_quotes:
        quotes.append({
            'text': quote,
            'quote_type': 'blue-quote'
        })
    
    return quotes

def save_quotes(quotes: List[Dict[str, str]], email: Email, session) -> None:
    """
    Save extracted quotes to the database.
    
    Args:
        quotes: List of extracted quotes with metadata
        email: Associated Email object
        session: Database session
    """
    for quote_data in quotes:
        # Check if this quote already exists
        existing_quote = session.execute(
            select(Quote)
            .where(Quote.text == quote_data['text'])
        ).scalar_one_or_none()
        
        if existing_quote:
            # Link existing quote to this email
            email.quotes.append(existing_quote)
        else:
            # Create new quote
            quote = Quote(
                text=quote_data['text'],
                quote_type=quote_data['quote_type']
            )
            email.quotes.append(quote)
            session.add(quote)

@quotes_bp.route('/quotes')
@require_auth
def list_quotes():
    """Display all tracked quotes with their metadata."""
    session = Session()
    try:
        quotes = session.execute(
            select(Quote)
            .order_by(Quote.created_at.desc())
        ).scalars().all()
        
        return render_template(
            'quotes.html',
            quotes=quotes,
            quote_types=QUOTE_TYPES
        )
    finally:
        session.close()

@quotes_bp.route('/quotes/<int:quote_id>/edit', methods=['GET', 'POST'])
@require_auth
def edit_quote(quote_id):
    """Edit a specific quote's metadata."""
    db_session = Session()
    try:
        quote = db_session.get(Quote, quote_id)
        if not quote:
            return "Quote not found", 404
            
        if request.method == 'POST':
            quote.author = request.form.get('author')
            quote.source = request.form.get('source')
            quote.commentary = request.form.get('commentary')
            quote.quote_type = request.form.get('quote_type')
            
            db_session.commit()
            return redirect(url_for('quotes.list_quotes'))
            
        return render_template(
            'edit_quote.html',
            quote=quote,
            quote_types=QUOTE_TYPES
        )
    finally:
        db_session.close()
