from flask import Blueprint, request, render_template, url_for, redirect
from sqlalchemy import select
from typing import Dict, Any
from common.base.logging_config import get_logger

from web.decorators.auth import require_auth
from models.database import db
from models.models import Quote
from models.quotes import (
    QUOTE_TYPES,
    get_quotes_by_type,
    update_quote,
    delete_quote,
    search_quotes,
    QuoteValidationError
)

logger = get_logger(__name__)

quotes_bp = Blueprint('quotes', __name__)

@quotes_bp.route('/quotes')
@require_auth
def list_quotes():
    """Display all tracked quotes with their metadata."""
    with db.session() as db_session:
        quote_type = request.args.get('type')
        search_term = request.args.get('search')
        
        if search_term:
            quotes = search_quotes(db_session, search_term, quote_type)
        else:
            quotes = get_quotes_by_type(db_session, quote_type)
        
        return render_template(
            'quotes/quotes.html',
            quotes=quotes,
            quote_types=QUOTE_TYPES,
            current_type=quote_type,
            search_term=search_term
        )


@quotes_bp.route('/quotes/<int:quote_id>/edit', methods=['GET', 'POST'])
@require_auth
def edit_quote(quote_id: int):
    """Edit a specific quote's metadata."""
    with db.session() as db_session:
        quote = db_session.get(Quote, quote_id)
        if not quote:
            return "Quote not found", 404
            
        if request.method == 'POST':
            try:
                quote_data = {
                    'text': quote.text,  # Preserve original text
                    'quote_type': request.form.get('quote_type'),
                    'author': request.form.get('author'),
                    'source': request.form.get('source'),
                    'date': request.form.get('date'),
                    'commentary': request.form.get('commentary')
                }
                
                updated_quote = update_quote(db_session, quote_id, quote_data)
                if updated_quote:
                    return redirect(url_for('quotes.list_quotes'))
                return "Quote not found", 404
                
            except QuoteValidationError as e:
                return render_template(
                    'quotes/edit_quote.html',
                    quote=quote,
                    quote_types=QUOTE_TYPES.keys(),
                    error=str(e)
                )
            
        return render_template(
            'quotes/edit_quote.html',
            quote=quote,
            quote_types=QUOTE_TYPES.keys()
        )


@quotes_bp.route('/quotes/<int:quote_id>/delete', methods=['POST'])
@require_auth
def delete_quote(quote_id: int):
    """Delete a quote."""
    with db.session() as db_session:
        if delete_quote(db_session, quote_id):
            return redirect(url_for('quotes.list_quotes'))
        return "Quote not found", 404


@quotes_bp.route('/quotes/search')
@require_auth
def search():
    """Search quotes endpoint."""
    search_term = request.args.get('q', '').strip()
    quote_type = request.args.get('type')
    
    if not search_term:
        return redirect(url_for('quotes.list_quotes'))
        
    return redirect(url_for('quotes.list_quotes', 
                          search=search_term, 
                          type=quote_type))
