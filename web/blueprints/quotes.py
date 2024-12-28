from flask import Blueprint, request, render_template, url_for, redirect
from sqlalchemy.orm import joinedload
import logging
from typing import Dict, Any, Optional, List, Tuple

from common.database import setup_database
Session, db_success = setup_database()

from common.models import Email
from common.colorscheme import ColorScheme
from .auth import require_auth

quotes_bp = Blueprint('quotes', __name__)

QUOTE_TYPES = ['yellow-quote', 'yellow-snowclone', 'blue-quote']
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
            return redirect(url_for('list_quotes'))
            
        return render_template(
            'edit_quote.html',
            quote=quote,
            quote_types=QUOTE_TYPES
        )
    finally:
        db_session.close()
