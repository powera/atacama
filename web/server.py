from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import re
from typing import Dict, List
from flask import Flask, request, jsonify, render_template_string
import logging
from waitress import serve
import imaplib
import email
import threading
import time
import os
from email.header import decode_header
import json

app = Flask(__name__)
Base = declarative_base()

class ColorScheme:
    COLORS = {
        'xantham': 'infrared',  # sarcastic, overconfident
        'red': 'red',          # forceful, certain
        'orange': 'orange',    # counterpoint
        'yellow': 'yellow',    # quotes
        'green': 'green',      # technical explanations
        'teal': 'teal',       # LLM output
        'blue': 'blue',       # voice from beyond
        'violet': 'violet',    # serious
        'mogue': 'ultraviolet', # actions taken
        'gray': 'gray'        # past stories
    }

class Email(Base):
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(255))
    content = Column(Text)
    processed_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailProcessor:
    def __init__(self):
        self.color_patterns = {
            'xantham': r'<xantham>(.*?)(</xantham>|$)',
            'red': r'<red>(.*?)(</red>|$)',
            'orange': r'<orange>(.*?)(</orange>|$)',
            'yellow': r'<yellow>(.*?)(</yellow>|$)',
            'green': r'<green>(.*?)(</green>|$)',
            'teal': r'<teal>(.*?)(</teal>|$)',
            'blue': r'<blue>(.*?)(</blue>|$)',
            'violet': r'<violet>(.*?)(</violet>|$)',
            'mogue': r'<mogue>(.*?)(</mogue>|$)',
            'gray': r'<gray>(.*?)(</gray>|$)'
        }
        
    def process_email(self, content: str) -> str:
        """Process email content and wrap color tags in HTML/CSS."""
        processed = content
        
        for color, pattern in self.color_patterns.items():
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                text = match.group(1)
                if color == 'teal':
                    replacement = f'<span style="color: {ColorScheme.COLORS[color]}; font-family: Comic Sans MS;">{text}</span>'
                else:
                    replacement = f'<span style="color: {ColorScheme.COLORS[color]};">{text}</span>'
                processed = processed.replace(match.group(0), replacement)
                
        return processed

# Database setup
def setup_database():
    """Initialize the database and create tables."""
    engine = create_engine('sqlite:///emails.db')
    Base.metadata.create_all(engine)
    return engine

# Initialize database and session
engine = setup_database()
Session = sessionmaker(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@app.route('/process', methods=['POST'])
def process_email():
    """API endpoint to process and store emails."""
    try:
        data = request.get_json()
        
        if not data or 'subject' not in data or 'content' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        session = Session()
        processor = EmailProcessor()
        
        processed_content = processor.process_email(data['content'])
        
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
def get_email(email_id):
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


class EmailFetcher:
    def __init__(self, host='localhost', port=143, username=None, password=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.processor = EmailProcessor()
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """Establish IMAP connection."""
        try:
            self.imap = imaplib.IMAP4(self.host, self.port)
            if self.username and self.password:
                self.imap.login(self.username, self.password)
            return True
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {str(e)}")
            return False

    def fetch_emails(self, session):
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
                    
                    # Extract content from email
                    content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                content += part.get_payload(decode=True).decode()
                    else:
                        content = msg.get_payload(decode=True).decode()
                    
                    # Process and store email
                    processed_content = self.processor.process_email(content)
                    email_obj = Email(
                        subject=subject,
                        content=content,
                        processed_content=processed_content
                    )
                    
                    session.add(email_obj)
                    session.commit()
                    
                    self.logger.info(f"Processed incoming email: {subject}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing message {msg_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error in fetch_emails: {str(e)}")
        
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

class EmailFetcherDaemon(threading.Thread):
    def __init__(self, config_path='email_config.json'):
        super().__init__(daemon=True)
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.running = True
        self.load_config()
        
    def load_config(self):
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
            self.logger.error(f"Error loading config: {str(e)}")
            # Use defaults if config loading fails
            self.interval = 300
            self.imap_config = {
                'host': 'localhost',
                'port': 143,
                'username': None,
                'password': None
            }

    def run(self):
        """Run the email fetcher daemon."""
        self.logger.info("Starting email fetcher daemon...")
        fetcher = EmailFetcher(**self.imap_config)
        
        while self.running:
            session = Session()
            try:
                fetcher.fetch_emails(session)
            except Exception as e:
                self.logger.error(f"Error in fetcher daemon: {str(e)}")
            finally:
                session.close()
            
            time.sleep(self.interval)
    
    def stop(self):
        """Stop the daemon gracefully."""
        self.running = False

# HTML template for landing page
LANDING_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Atacama Email Processor</title>
    <link rel="stylesheet" href="/css/landing.css">
</head>
<body>
    <h1>Atacama Email Processor</h1>
    
    <div class="status">
        <h2>Service Status</h2>
        <p>Server is running and processing emails with custom color formatting.</p>
        <p>Database Status: {{ db_status }}</p>
    </div>

    <div class="endpoints">
        <h2>Available Endpoints</h2>
        <ul>
            <li><code>POST /process</code> - Process and store new emails</li>
            <li><code>GET /emails/{id}</code> - Retrieve processed email by ID</li>
        </ul>
    </div>

    <h2>Recent Emails</h2>
    {% if emails %}
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Subject</th>
                <th>Preview</th>
                <th>Received</th>
            </tr>
        </thead>
        <tbody>
            {% for email in emails %}
            <tr>
                <td>{{ email.id }}</td>
                <td>
                    <a href="/emails/{{ email.id }}" class="email-link">
                        {{ email.subject or '(No Subject)' }}
                    </a>
                </td>
                <td class="email-preview">{{ email.content[:100] }}...</td>
                <td class="timestamp">{{ email.created_at_formatted }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="no-emails">
        No emails processed yet
    </div>
    {% endif %}
</body>
</html>
"""

@app.route('/css/<path:filename>')
def serve_css(filename):
    """Serve CSS files from the css directory."""
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    return send_from_directory(css_dir, filename)

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
    
    return render_template_string(
        LANDING_PAGE_TEMPLATE,
        db_status=db_status,
        emails=emails
    )

def run_server():
    """Run the server and start the email fetcher daemon."""
    # Start email fetcher daemon
    fetcher_daemon = EmailFetcherDaemon()
    fetcher_daemon.start()
    
    logger.info("Starting email processor server...")
    try:
        serve(app, host='0.0.0.0', port=5000)
    finally:
        # Ensure daemon is stopped when server stops
        fetcher_daemon.stop()
        fetcher_daemon.join()


if __name__ == "__main__":
    run_server()
