from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory
from waitress import serve
import os
import json
import logging
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests

from common.database import setup_database
from common.models import Email
from common.colorscheme import ColorScheme
from web.email_fetcher import EmailFetcherDaemon

app = Flask(__name__)
logger = logging.getLogger(__name__)
Session, db_success = setup_database()
color_processor = ColorScheme()

def require_auth(f):
    """Decorator to require Google authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'No authorization header'}), 401
            
        try:
            # Verify the ID token
            token = auth_header.split(' ')[1]
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                os.getenv('GOOGLE_CLIENT_ID')
            )
            
            # Token is valid, store user info in request
            request.user = {
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', '')
            }
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
            
    return decorated_function

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
            'processed_content': processed_content
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()

@app.route('/messages/<int:message_id>', methods=['GET'])
@require_auth
def get_message(message_id: int) -> tuple[Dict[str, Any], int]:
    """Retrieve a processed message by ID."""
    try:
        session = Session()
        message = session.query(Email).filter(Email.id == message_id).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
            
        return jsonify({
            'id': message.id,
            'subject': message.subject,
            'content': message.content,
            'processed_content': message.processed_content,
            'created_at': message.created_at.isoformat()
        })
        
    finally:
        session.close()

@app.route('/')
@require_auth
def landing_page():
    """Serve the landing page with basic service information and message list."""
    try:
        session = Session()
        
        # Test database connection
        session.execute(text('SELECT 1'))
        db_status = "Connected"
        
        # Fetch recent messages
        messages = session.query(Email).order_by(Email.created_at.desc()).limit(50).all()
        
        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        db_status = f"Error: {str(e)}"
        messages = []
    finally:
        session.close()
    
    return render_template_string(
        'landing.html',
        db_status=db_status,
        messages=messages,
        user=request.user
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
            
            return render_template('submit.html', success=True)
            
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
