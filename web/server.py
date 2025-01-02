#!/usr/bin/python3

""" Web server for atacama. """

from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory, session, url_for, redirect
from waitress import serve
import os
import json
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps
from pathlib import Path

from logging_config import get_logger
logger = get_logger(__name__)

from common.database import setup_database
from common.models import Email, Quote, email_quotes
from common.colorscheme import ColorScheme
color_processor = ColorScheme()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')  # Change in production
Session, db_success = setup_database()

from request_logger import RequestLogger
request_logger = RequestLogger(app, log_dir='request_logs')

from web.blueprints.auth import require_auth

# Serve Quotes HTML pages
from web.blueprints.quotes import quotes_bp
app.register_blueprint(quotes_bp)

# Serve CSS, JS, etc.
from web.blueprints.static import static_bp
app.register_blueprint(static_bp)

# Login, logout, Google Auth callbacks
from web.blueprints.auth import auth_bp
app.register_blueprint(auth_bp)

# Message display handlers
from web.blueprints.messages import messages_bp
app.register_blueprint(messages_bp)

# Submit message form
from web.blueprints.submit import submit_bp
app.register_blueprint(submit_bp)

# Debug handlers
from web.blueprints.debug import debug_bp
app.register_blueprint(debug_bp)

# Error handlers
from web.blueprints.errors import errors_bp
app.register_blueprint(errors_bp)

@app.route('/messages/<int:message_id>/reprocess', methods=['POST'])
@require_auth
def reprocess_message(message_id: int):
    """Reprocess an existing message's content."""
    try:
        db_session = Session()
        message = db_session.query(Email).options(
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = {}
        
        # Update annotations if provided
        llm_annotations = data.get('llm_annotations',
            json.loads(message.llm_annotations or '{}'))
        if 'llm_annotations' in data:
            message.llm_annotations = json.dumps(llm_annotations)
        
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
            llm_annotations=llm_annotations,
            message=message,
            db_session=db_session,
        )
        
        db_session.commit()
        
        logger.info(f"Reprocessed message {message_id}")
        
        
        if request.headers.get('Accept', '').startswith('text/html'):
            template = 'message.html'
            return render_template(
                template,
                message=message,
                created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                raw_content=message.content,
                quotes=message.quotes
            )
        else: 
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
        db_session.close()


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
    user = session.get('user')

    return render_template(
        'landing.html',
        db_status=db_status,
        messages=messages,
        user=user
    )


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
