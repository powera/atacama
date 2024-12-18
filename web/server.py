from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory, session, url_for
from waitress import serve
import os
import json
import logging
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests
from pathlib import Path

from common.database import setup_database
from common.models import Email
from common.colorscheme import ColorScheme
from web.email_fetcher import EmailFetcherDaemon

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')  # Change in production
logger = logging.getLogger(__name__)
Session, db_success = setup_database()
color_processor = ColorScheme()

# Auth configuration
DEV_AUTH_PATH = os.getenv('DEV_AUTH_PATH', '/.dev-auth')
DEFAULT_SECRET_PATH = os.path.expanduser('~/.atacama_secret')

def read_auth_code() -> str:
    """
    Read authentication code from secret file.
    
    :return: Authentication code from file or default if file not found
    """
    secret_path = os.getenv('ATACAMA_SECRET_PATH', DEFAULT_SECRET_PATH)
    try:
        with open(secret_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Secret file not found at {secret_path}, using default")
        return 'atacama-dev'
    except Exception as e:
        logger.error(f"Error reading secret file: {str(e)}")
        return 'atacama-dev'

def require_auth(f):
    """Decorator to require either Google or dev authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for dev auth first
        if session.get('dev_authenticated'):
            return f(*args, **kwargs)

        # Then check Google auth
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Authentication required'}), 401
            
        try:
            token = auth_header.split(' ')[1]
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                os.getenv('GOOGLE_CLIENT_ID')
            )
            
            request.user = {
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', '')
            }
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            return jsonify({'error': 'Invalid authentication'}), 401
            
    return decorated_function

@app.route(DEV_AUTH_PATH, methods=['GET', 'POST'])
def dev_auth():
    """Development authentication endpoint."""
    if request.method == 'POST':
        if request.form.get('passcode') == read_auth_code():
            session['dev_authenticated'] = True
            return jsonify({'status': 'authenticated'})
        return jsonify({'error': 'Invalid passcode'}), 401

    return '''
        <form method="post">
            <input type="password" name="passcode" placeholder="Enter passcode">
            <input type="submit" value="Authenticate">
        </form>
    '''

def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Helper function to retrieve a message by ID.
    
    :param message_id: ID of the message to retrieve
    :return: Email object if found, None otherwise
    """
    try:
        session = Session()
        return session.query(Email).filter(Email.id == message_id).first()
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
        processed_content = color_processor.process_content(data['content'])
        
        message = Email(
            subject=data['subject'],
            content=data['content'],
            processed_content=processed_content
        )
        
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
    
    # Return HTML if requested
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'message.html',
            message=message,
            created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
            
    # Otherwise return JSON
    return jsonify({
        'id': message.id,
        'subject': message.subject,
        'content': message.content,
        'processed_content': message.processed_content,
        'created_at': message.created_at.isoformat()
    })

@app.route('/messages/<int:message_id>/reprocess', methods=['POST'])
@require_auth
def reprocess_message(message_id: int):
    """Reprocess an existing message's content."""
    try:
        session = Session()
        message = session.query(Email).filter(Email.id == message_id).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
            
        message.processed_content = color_processor.process_content(message.content)
        session.commit()
        
        logger.info(f"Reprocessed message {message_id}")
        
        if request.headers.get('Accept', '').startswith('text/html'):
            return render_template(
                'message.html',
                message=message,
                created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            )
            
        return jsonify({
            'id': message.id,
            'processed_content': message.processed_content
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
            created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
        
    finally:
        session.close()


# In server.py
@app.route('/')
def landing_page():
    """Serve the landing page with basic service information and message list."""
    try:
        db_session = Session()

        # Test database connection
        db_session.execute(text('SELECT 1'))
        db_status = "Connected"

        # Fetch recent messages
        messages = db_session.query(Email).order_by(Email.created_at.desc()).limit(50).all()

        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        db_status = f"Error: {str(e)}"
        messages = []
    finally:
        db_session.close()

    # Check if user is authenticated via dev auth
    user = None
    if session.get('dev_authenticated'):
        user = {'name': 'Developer'}
    # Or via Google auth (set in require_auth decorator)
    elif hasattr(request, 'user'):
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
            
            if not subject or not content:
                return render_template('submit.html', error='Subject and content are required')
                
            session = Session()
            processed_content = color_processor.process_content(content)
            
            message = Email(
                subject=subject,
                content=content,
                processed_content=processed_content
            )
            
            session.add(message)
            session.commit()
            
            view_url = url_for('get_message', message_id=message.id)
            return render_template('submit.html', success=True, view_url=view_url)
            
        except Exception as e:
            logger.error(f"Error processing form submission: {str(e)}")
            return render_template('submit.html', error=str(e))
            
        finally:
            session.close()
            
    return render_template('submit.html')

@app.route('/css/<path:filename>')
def serve_css(filename: str):
    """
    Serve CSS files from the css directory.

    :param filename: Name of the CSS file to serve
    :return: CSS file response
    """
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    return send_from_directory(css_dir, filename)

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
