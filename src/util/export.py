#!/usr/bin/env python3

"""Export messages from the Atacama database to JSON format."""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from sqlalchemy.orm import joinedload

# Gross hack for imports
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.database import db
from common.models import Email, Quote
from common.logging_config import get_logger

logger = get_logger(__name__)

def serialize_message(message: Email) -> Dict[str, Any]:
    """
    Serialize a message and its related data to a dictionary.
    
    :param message: Email object to serialize
    :return: Dictionary containing message data
    """
    return {
        'id': message.id,
        'subject': message.subject,
        'content': message.content,
        'processed_content': message.processed_content,
        'created_at': message.created_at.isoformat(),
        'parent_id': message.parent_id,
        'author': {
            'id': message.author.id,
            'email': message.author.email,
            'name': message.author.name
        } if message.author else None,
        'quotes': [{
            'id': quote.id,
            'text': quote.text,
            'quote_type': quote.quote_type,
            'author': quote.author,
            'source': quote.source,
            'commentary': quote.commentary,
            'created_at': quote.created_at.isoformat()
        } for quote in message.quotes],
        'chinese_annotations': json.loads(message.chinese_annotations) if message.chinese_annotations else None,
        'llm_annotations': json.loads(message.llm_annotations) if message.llm_annotations else None
    }

def export_messages(output_path: str, pretty: bool = True) -> None:
    """
    Export all messages from the database to a JSON file.
    
    :param output_path: Path where the JSON file should be saved
    :param pretty: Whether to format the JSON output for readability
    """
    with db.session() as db_session:
        
        # Query all messages with their relationships
        messages = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes),
            joinedload(Email.author)
        ).order_by(Email.created_at).all()
        
        # Serialize all messages
        data = {
            'exported_at': datetime.utcnow().isoformat(),
            'total_messages': len(messages),
            'messages': [serialize_message(msg) for msg in messages]
        }
        
        # Create output directory if it doesn't exist
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
                
        logger.info(f"Successfully exported {len(messages)} messages to {output_path}")
        


def main() -> None:
    """Main entry point for the export script."""
    parser = argparse.ArgumentParser(description='Export Atacama messages to JSON')
    parser.add_argument('--output', '-o', default='messages_export.json',
                       help='Output JSON file path')
    parser.add_argument('--pretty', '-p', action='store_true',
                       help='Format JSON output for readability')
    
    args = parser.parse_args()
    
    try:
        export_messages(args.output, args.pretty)
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
