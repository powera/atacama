#!/usr/bin/python3

""" Web server for atacama. """

from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory, session, url_for, redirect
from waitress import serve
import os
import json
import logging
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps
from pathlib import Path

from common.database import setup_database
from common.models import Email, Quote, email_quotes
from common.colorscheme import ColorScheme

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')  # Change in production
logger = logging.getLogger(__name__)
Session, db_success = setup_database()
color_processor = ColorScheme()

from web.blueprints.auth import require_auth

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

def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Helper function to retrieve a message by ID.
    
    :param message_id: ID of the message to retrieve
    :return: Email object if found, None otherwise
    """
    session = Session()
    try:
        # Load the message and its relationships in one query
        return session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
    except Exception as e:
        logger.error(f"Error retrieving message {message_id}: {str(e)}")
        return None
    finally:
        session.close()

@app.route('/messages/<int:message_id>', methods=['GET'])
def get_message(message_id: int):
    """Retrieve a processed message by ID."""
    message = get_message_by_id(message_id)
    
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Get print mode from query params
    print_mode = request.args.get('print', '').lower() == 'true'
    
    # Return HTML if requested
    if request.headers.get('Accept', '').startswith('text/html'):
        template = 'message_print.html' if print_mode else 'message.html'
        return render_template(
            template,
            message=message,
            created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            raw_content=message.content,  # For two-screen editing
            quotes=message.quotes
        )
            
    # Otherwise return JSON
    return jsonify({
        'id': message.id,
        'subject': message.subject,
        'content': message.content,
        'processed_content': message.processed_content,
        'created_at': message.created_at.isoformat(),
        'parent_id': message.parent_id,
        'llm_annotations': json.loads(message.llm_annotations or '{}'),
        'quotes': [{'text': q.text, 'type': q.quote_type} for q in message.quotes]
    })

@app.route('/messages/<int:message_id>/reprocess', methods=['POST'])
@require_auth
def reprocess_message(message_id: int):
    """Reprocess an existing message's content."""
    try:
        session = Session()
        message = session.query(Email).options(
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = {}
        
        llm_annotations = data.get('llm_annotations',
            json.loads(message.llm_annotations or '{}'))
            
        message.processed_content = color_processor.process_content(
            message.content,
            llm_annotations=llm_annotations
        )
        
        # Update annotations if provided
        if 'llm_annotations' in data:
            message.llm_annotations = json.dumps(llm_annotations)
        
        # Re-process quotes
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

        quotes = extract_quotes(message.content)
        save_quotes(quotes, message, session)
        
        session.commit()
        
        logger.info(f"Reprocessed message {message_id}")
        
        # Get print mode from query params
        print_mode = request.args.get('print', '').lower() == 'true'
        
        if request.headers.get('Accept', '').startswith('text/html'):
            template = 'message_print.html' if print_mode else 'message.html'
            return render_template(
                template,
                message=message,
                created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                raw_content=message.content,
                quotes=message.quotes
            )
            
        return jsonify({
            'id': message.id,
            'processed_content': message.processed_content,
            'llm_annotations': llm_annotations,
            'quotes': [{'text': q.text, 'type': q.quote_type} for q in message.quotes]
        })
        
    except Exception as e:
        logger.error(f"Error reprocessing message: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        session.close()

@app.route('/recent')
def recent_message():
    """Show the most recent message."""
    try:
        session = Session()
        message = session.query(Email).order_by(Email.created_at.desc()).first()
        
        if not message:
            return render_template('message.html', error="No messages found")
            
        return render_template(
            'message.html',
            message=message,
            created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            raw_content=message.content,
        )
        
    finally:
        session.close()

@app.route('/stream')
def message_stream():
    """Show a stream of recent messages."""
    try:
        session = Session()
        messages = session.query(Email).options(
            joinedload(Email.quotes)
        ).order_by(Email.created_at.desc()).limit(10).all()
        
        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            
        return render_template(
            'stream.html',
            messages=messages
        )
        
    finally:
        session.close()


@app.route('/')
def landing_page():
    """Serve the landing page with basic service information and message list."""
    try:
        db_session = Session()

        # Test database connection
        db_session.execute(text('SELECT 1'))
        db_status = "Connected"

        # Fetch recent messages with their relationships
        messages = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).order_by(Email.created_at.desc()).limit(50).all()

        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        db_status = f"Error: {str(e)}"
        messages = []
    finally:
        db_session.close()

    # Check if user is authenticated via Google auth
    user = None
    if hasattr(request, 'user'):
        user = request.user

    return render_template(
        'landing.html',
        db_status=db_status,
        messages=messages,
        user=user
    )

# Serve Quotes HTML pages
from web.blueprints.quotes import quotes_bp
app.register_blueprint(quotes_bp)

# Serve CSS, JS, etc.
from web.blueprints.static import static_bp
app.register_blueprint(static_bp)

# Login, logout, Google Auth callbacks
from web.blueprints.auth import auth_bp
app.register_blueprint(auth_bp)

# Submit message form
from web.blueprints.submit import submit_bp
app.register_blueprint(submit_bp)

# Debug handlers
from web.blueprints.debug import debug_bp
app.register_blueprint(debug_bp)

def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """Run the server and start the email fetcher daemon."""
    if not db_success:
        logger.error("Database initialization failed, cannot start web server")
        return
        
    logger.info(f"Starting message processor server on {host}:{port}")
    try:
        serve(app, host=host, port=port)
    finally:
        fetcher_daemon.stop()
        fetcher_daemon.join()
