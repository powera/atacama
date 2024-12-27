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
from google.oauth2 import id_token
from google.auth.transport import requests
from pathlib import Path

from common.database import setup_database
from common.models import Email, Quote, email_quotes
from common.colorscheme import ColorScheme
from web.email_fetcher import EmailFetcherDaemon

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')  # Change in production
logger = logging.getLogger(__name__)
Session, db_success = setup_database()
color_processor = ColorScheme()
QUOTE_TYPES = ['yellow-quote', 'yellow-snowclone', 'blue-quote']

def require_auth(f):
    """Decorator to require either Google or dev authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check session auth for web users
        if 'user' in session:
            request.user = session['user']
            return f(*args, **kwargs)

        # Then check Bearer token auth for API requests
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                idinfo = id_token.verify_oauth2_token(
                    token,
                    requests.Request(),
                    os.getenv('GOOGLE_CLIENT_ID')
                )
                
                # Verify the token is not expired and audience matches
                if idinfo['aud'] != os.getenv('GOOGLE_CLIENT_ID'):
                    raise ValueError('Invalid audience')
                if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                    raise ValueError('Invalid issuer')
                
                request.user = {
                    'email': idinfo['email'],
                    'name': idinfo.get('name', ''),
                    'picture': idinfo.get('picture', '')
                }
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Auth error: {str(e)}")
                return jsonify({'error': 'Invalid authentication'}), 401

        # No valid auth found - redirect web users, return 401 for API
        if request.headers.get('Accept', '').startswith('text/html'):
            return redirect(url_for('login'))
        return jsonify({'error': 'Authentication required'}), 401


# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

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

@app.route('/process', methods=['POST'])
@require_auth
def process_message() -> tuple[Dict[str, Any], int]:
    """API endpoint to process and store messages."""
    try:
        data = request.get_json()
        
        if not data or 'subject' not in data or 'content' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        session = Session()
        
        # Process content with enhanced features
        processed_content = color_processor.process_content(
            data['content'],
            llm_annotations=data.get('llm_annotations')
        )
        
        # Create message object
        message = Email(
            subject=data['subject'],
            content=data['content'],
            processed_content=processed_content,
            llm_annotations=json.dumps(data.get('llm_annotations', {}))
        )
        
        # Handle message chain if parent_id is provided
        if 'parent_id' in data:
            parent = session.query(Email).get(data['parent_id'])
            if parent:
                message.parent = parent
        
        # Extract and save quotes
        quotes = extract_quotes(data['content'])
        save_quotes(quotes, message, session)
        
        session.add(message)
        session.commit()
        
        logger.info(f"Processed message with subject: {data['subject']}")
        
        return jsonify({
            'id': message.id,
            'processed_content': processed_content,
            'view_url': url_for('get_message', message_id=message.id)
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
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

@app.route('/quotes')
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

@app.route('/quotes/<int:quote_id>/edit', methods=['GET', 'POST'])
@require_auth
def edit_quote(quote_id):
    """Edit a specific quote's metadata."""
    session = Session()
    try:
        quote = session.get(Quote, quote_id)
        if not quote:
            return "Quote not found", 404
            
        if request.method == 'POST':
            quote.author = request.form.get('author')
            quote.source = request.form.get('source')
            quote.commentary = request.form.get('commentary')
            quote.quote_type = request.form.get('quote_type')
            
            session.commit()
            return redirect(url_for('list_quotes'))
            
        return render_template(
            'edit_quote.html',
            quote=quote,
            quote_types=QUOTE_TYPES
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

@app.route('/submit', methods=['GET', 'POST'])
@require_auth
def submit_form():
    """Handle message submission via HTML form."""
    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '')
            content = request.form.get('content', '')
            parent_id = request.form.get('parent_id')
            
            if not subject or not content:
                return render_template('submit.html', error='Subject and content are required')
                
            session = Session()
            processed_content = color_processor.process_content(content)
            
            message = Email(
                subject=subject,
                content=content,
                processed_content=processed_content,
            )
            
            # Handle message chain if parent_id is provided
            if parent_id and parent_id.strip():
                try:
                    parent_id = int(parent_id)
                    parent = session.query(Email).get(parent_id)
                    if parent:
                        message.parent = parent
                    else:
                        logger.warning(f"Parent message {parent_id} not found")
                except ValueError:
                    logger.warning(f"Invalid parent_id format: {parent_id}")
            
            # Extract and save quotes
            quotes = extract_quotes(content)
            save_quotes(quotes, message, session)
            
            session.add(message)
            session.commit()
            
            view_url = url_for('get_message', message_id=message.id)
            return render_template('submit.html', success=True, view_url=view_url)
            
        except Exception as e:
            logger.error(f"Error processing form submission: {str(e)}")
            return render_template('submit.html', error=str(e))
            
        finally:
            session.close()
        # END of processing submission of message by POST
            
    # Get recent messages for the dropdown
    session = Session()
    try:
        recent_messages = session.query(Email).order_by(
            Email.created_at.desc()
        ).limit(50).all()
    except Exception as e:
        logger.error(f"Error fetching recent messages: {str(e)}")
        recent_messages = []
    finally:
        session.close()
    return render_template('submit.html', recent_messages=recent_messages)

@app.route('/js/<path:filename>')
def serve_js(filename: str):
    """
    Serve JS files from the js directory.

    :param filename: Name of the JS file to serve
    :return: JS file response
    """
    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
    return send_from_directory(js_dir, filename)

@app.route('/css/<path:filename>')
def serve_css(filename: str):
    """
    Serve CSS files from the css directory.

    :param filename: Name of the CSS file to serve
    :return: CSS file response
    """
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    return send_from_directory(css_dir, filename)

@app.route('/login')
def login():
    """Serve the login page with Google Sign-In button."""
    # If user is already logged in, redirect to home
    if 'user' in session:
        return redirect(url_for('landing_page'))
        
    return render_template(
        'login.html',
        client_id=GOOGLE_CLIENT_ID
    )

@app.route('/auth/google', methods=['POST'])
def google_auth():
    """Handle Google Sign-In callback."""
    try:
        token = request.json.get('credential')
        if not token:
            return jsonify({'error': 'No credential provided'}), 400
            
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        if idinfo['aud'] != GOOGLE_CLIENT_ID:
            return jsonify({'error': 'Invalid audience'}), 401
            
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            return jsonify({'error': 'Invalid issuer'}), 401
            
        # Store user info in session
        session['user'] = {
            'email': idinfo['email'],
            'name': idinfo.get('name', ''),
            'picture': idinfo.get('picture', '')
        }
        
        return jsonify({'success': True, 'redirect': url_for('landing_page')})
        
    except Exception as e:
        logger.error(f"Google auth error: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 401

@app.route('/logout')
def logout():
    """Clear the session and redirect to login."""
    session.clear()
    return redirect(url_for('login'))

def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """Run the server and start the email fetcher daemon."""
    if not db_success:
        logger.error("Database initialization failed, cannot start web server")
        return
        
    fetcher_daemon = EmailFetcherDaemon()
    fetcher_daemon.start()
    
    logger.info(f"Starting message processor server on {host}:{port}")
    try:
        serve(app, host=host, port=port)
    finally:
        fetcher_daemon.stop()
        fetcher_daemon.join()
