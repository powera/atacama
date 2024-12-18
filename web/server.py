from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory
from waitress import serve
import imaplib
import email
import threading
import time
import os
import json
import logging
from email.header import decode_header
from sqlalchemy import text
from datetime import datetime
from typing import Optional, Dict, Any

from common.database import setup_database
from common.models import Email
from common.colorscheme import ColorScheme

app = Flask(__name__)
logger = logging.getLogger(__name__)
Session, db_success = setup_database()
color_processor = ColorScheme()

class EmailFetcher:
    def __init__(self, host: str = 'localhost', port: int = 143, username: Optional[str] = None, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
    def connect(self) -> bool:
        """Establish IMAP connection."""
        try:
            self.imap = imaplib.IMAP4(self.host, self.port)
            if self.username and self.password:
                self.imap.login(self.username, self.password)
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed: {str(e)}")
            return False

    def fetch_emails(self, session) -> None:
        """Fetch and process new emails."""
        try:
            if not self.connect():
                return
            
            self.imap.select('INBOX')
            _, messages = self.imap.search(None, 'UNSEEN')
            
            for msg_num in messages[0].split():
                try:
                    _, msg_data = self.imap.fetch(msg_num, '(RFC822)')
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)
                    
                    subject = decode_header(msg['subject'])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()
                    
                    content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                content += part.get_payload(decode=True).decode()
                    else:
                        content = msg.get_payload(decode=True).decode()
                    
                    processed_content = color_processor.process_content(content)
                    email_obj = Email(
                        subject=subject,
                        content=content,
                        processed_content=processed_content
                    )
                    
                    session.add(email_obj)
                    session.commit()
                    
                    logger.info(f"Processed incoming email: {subject}")
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in fetch_emails: {str(e)}")
        
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

class EmailFetcherDaemon(threading.Thread):
    def __init__(self, config_path: str = 'email_config.json'):
        super().__init__(daemon=True)
        self.config_path = config_path
        self.running = True
        self.load_config()
        
    def load_config(self) -> None:
        """Load IMAP configuration from file."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            self.interval = config.get('fetch_interval', 300)  # default 5 minutes
            self.imap_config = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 143),
                'username': config.get('username'),
                'password': config.get('password')
            }
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            self.interval = 300
            self.imap_config = {
                'host': 'localhost',
                'port': 143,
                'username': None,
                'password': None
            }

    def run(self) -> None:
        """Run the email fetcher daemon."""
        logger.info("Starting email fetcher daemon...")
        fetcher = EmailFetcher(**self.imap_config)
        
        while self.running:
            session = Session()
            try:
                fetcher.fetch_emails(session)
            except Exception as e:
                logger.error(f"Error in fetcher daemon: {str(e)}")
            finally:
                session.close()
            
            time.sleep(self.interval)
    
    def stop(self) -> None:
        """Stop the daemon gracefully."""
        self.running = False

@app.route('/process', methods=['POST'])
def process_email() -> tuple[Dict[str, Any], int]:
    """API endpoint to process and store emails."""
    try:
        data = request.get_json()
        
        if not data or 'subject' not in data or 'content' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        session = Session()
        processed_content = color_processor.process_content(data['content'])
        
        email = Email(
            subject=data['subject'],
            content=data['content'],
            processed_content=processed_content
        )
        
        session.add(email)
        session.commit()
        
        logger.info(f"Processed email with subject: {data['subject']}")
        
        return jsonify({
            'id': email.id,
            'processed_content': processed_content
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()

@app.route('/emails/<int:email_id>', methods=['GET'])
def get_email(email_id: int) -> tuple[Dict[str, Any], int]:
    """Retrieve a processed email by ID."""
    try:
        session = Session()
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            return jsonify({'error': 'Email not found'}), 404
            
        return jsonify({
            'id': email.id,
            'subject': email.subject,
            'content': email.content,
            'processed_content': email.processed_content,
            'created_at': email.created_at.isoformat()
        })
        
    finally:
        session.close()

@app.route('/')
def landing_page():
    """Serve the landing page with basic service information and email list."""
    try:
        session = Session()
        
        # Test database connection
        session.execute(text('SELECT 1'))
        db_status = "Connected"
        
        # Fetch recent emails
        emails = session.query(Email).order_by(Email.created_at.desc()).limit(50).all()
        
        # Format timestamps
        for email in emails:
            email.created_at_formatted = email.created_at.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        db_status = f"Error: {str(e)}"
        emails = []
    finally:
        session.close()
    
    return render_template(
        'landing.html',
        db_status=db_status,
        emails=emails
    )


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
    
    logger.info(f"Starting email processor server on {host}:{port}")
    try:
        serve(app, host=host, port=port)
    finally:
        fetcher_daemon.stop()
        fetcher_daemon.join()
