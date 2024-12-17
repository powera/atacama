from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import re
from typing import Dict, List
from flask import Flask, request, jsonify
import logging
from waitress import serve

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

def run_server():
    """Run the server using waitress for production deployment."""
    logger.info("Starting email processor server...")
    serve(app, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    run_server()
