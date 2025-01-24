#!/usr/bin/env python3

"""Import messages from JSON format into the Atacama database."""

import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

# Gross hack for imports
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.database import db
from common.models import Email, Quote, User, get_or_create_user
from common.logging_config import get_logger

logger = get_logger(__name__)

class ImportError(Exception):
    """Custom exception for import errors."""
    pass

def generate_message_hash(msg_data: Dict[str, Any]) -> str:
    """
    Generate a unique hash for message content to detect duplicates.
    
    :param msg_data: Message data from import file
    :return: SHA-256 hash of key message fields
    """
    author_email = msg_data.get('author', {}).get('email', '')
    hash_content = f"{msg_data['subject']}|{msg_data['content']}|{author_email}"
    return hashlib.sha256(hash_content.encode('utf-8')).hexdigest()

def find_duplicate_message(db_session, msg_data: Dict[str, Any]) -> Optional[Email]:
    """
    Check if a message already exists in the database.
    
    :param db_session: Database session
    :param msg_data: Message data from import
    :return: Existing Email object if found, None otherwise
    """
    author_email = msg_data.get('author', {}).get('email', '')
    return db_session.query(Email).join(Email.author).filter(
        Email.subject == msg_data['subject'],
        Email.content == msg_data['content'],
        User.email == author_email
    ).first()

def get_or_create_author(db_session, author_data: Optional[Dict[str, Any]]) -> Optional[User]:
    """
    Get existing user or create new one from import data.
    
    :param db_session: Database session
    :param author_data: Author data from import
    :return: User object or None if no author data
    """
    if not author_data:
        return None
        
    return get_or_create_user(db_session, {
        "email": author_data["email"],
        "name": author_data["name"]
    })

def create_quotes(db_session, quotes_data: List[Dict[str, Any]], message: Email) -> None:
    """
    Create quotes for a message from import data.
    
    :param db_session: Database session
    :param quotes_data: List of quote data from import
    :param message: Email object to associate quotes with
    """
    for quote_data in quotes_data:
        quote = Quote(
            text=quote_data["text"],
            quote_type=quote_data["quote_type"],
            author=quote_data.get("author"),
            source=quote_data.get("source"),
            commentary=quote_data.get("commentary"),
            created_at=datetime.fromisoformat(quote_data["created_at"])
        )
        message.quotes.append(quote)
        db_session.add(quote)

def import_messages(input_path: str, skip_duplicates: bool = True) -> None:
    """
    Import messages from a JSON file into the database.
    
    :param input_path: Path to JSON file containing messages
    :param skip_duplicates: Whether to skip duplicate messages
    """
    # Read import file
    input_file = Path(input_path)
    if not input_file.exists():
        raise ImportError(f"Import file not found: {input_path}")
        
    with open(input_file, 'r', encoding='utf-8') as f:
        import_data = json.load(f)
        
    if 'messages' not in import_data:
        raise ImportError("Invalid import file format - missing 'messages' array")
        
    # Track processed hashes to detect duplicates within import file
    processed_hashes: Set[str] = set()
        
    with db.session() as db_session:
        # Track id mappings for parent relationships
        id_map = {}  # old_id -> new_id
        
        # First pass - create messages without parent relationships
        for msg_data in import_data['messages']:
            # Check for duplicates using content hash
            msg_hash = generate_message_hash(msg_data)
            
            if msg_hash in processed_hashes:
                logger.info(f"Skipping duplicate message within import: {msg_data['id']}")
                continue
                
            # Check for existing message in database
            existing = find_duplicate_message(db_session, msg_data) if skip_duplicates else None
            
            if existing:
                logger.info(f"Skipping duplicate message: {msg_data['id']}")
                id_map[msg_data['id']] = existing.id
                processed_hashes.add(msg_hash)
                continue
                
            # Create message
            message = Email(
                subject=msg_data['subject'],
                content=msg_data['content'],
                processed_content=msg_data['processed_content'],
                created_at=datetime.fromisoformat(msg_data['created_at']),
                channel=msg_data.get('channel', 'private'),
                chinese_annotations=json.dumps(msg_data.get('chinese_annotations')),
                llm_annotations=json.dumps(msg_data.get('llm_annotations'))
            )
            
            # Set author if present
            message.author = get_or_create_author(db_session, msg_data.get('author'))
            
            # Create associated quotes
            if msg_data.get('quotes'):
                create_quotes(db_session, msg_data['quotes'], message)
                
            try:
                db_session.add(message)
                db_session.flush()  # Get new ID
                id_map[msg_data['id']] = message.id
                processed_hashes.add(msg_hash)
            except IntegrityError as e:
                logger.error(f"Failed to import message {msg_data['id']}: {str(e)}")
                db_session.rollback()
                continue
                
        # Second pass - update parent relationships
        for msg_data in import_data['messages']:
            if msg_data.get('parent_id'):
                new_id = id_map.get(msg_data['id'])
                new_parent_id = id_map.get(msg_data['parent_id'])
                
                if new_id and new_parent_id:
                    message = db_session.query(Email).get(new_id)
                    if message:
                        message.parent_id = new_parent_id
                        
        try:
            db_session.commit()
            logger.info(f"Successfully imported {len(id_map)} messages")
        except Exception as e:
            logger.error(f"Failed to update parent relationships: {str(e)}")
            db_session.rollback()
            raise ImportError("Failed to update parent relationships")

def main() -> None:
    """Main entry point for the import script."""
    parser = argparse.ArgumentParser(description='Import Atacama messages from JSON')
    parser.add_argument('input', help='Input JSON file path')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Import duplicate messages instead of skipping them')
    
    args = parser.parse_args()
    
    try:
        import_messages(args.input, skip_duplicates=not args.force)
    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        exit(1)

if __name__ == '__main__':
    main()
