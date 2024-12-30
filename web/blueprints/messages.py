from flask import Blueprint, render_template, jsonify, request, session
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from common.database import setup_database
Session, db_success = setup_database()

from common.models import Email
from .auth import require_auth

messages_bp = Blueprint('messages', __name__)

def get_message_by_id(message_id: int) -> Optional[Email]:
    """
    Helper function to retrieve a message by ID with all relevant relationships.
    
    Args:
        message_id: ID of the message to retrieve
        
    Returns:
        Email object if found, None otherwise
    """
    db_session = Session()
    try:
        return db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
    except Exception as e:
        logger.error(f"Error retrieving message {message_id}: {str(e)}")
        return None
    finally:
        db_session.close()

def get_message_chain(message_id: int) -> List[Email]:
    """
    Retrieve the full chain of messages related to a given message ID.
    Includes the parent chain and all child messages.
    
    Args:
        message_id: ID of the message to get the chain for
        
    Returns:
        List of Email objects representing the chain, ordered chronologically
    """
    db_session = Session()
    try:
        # Get the target message with its relationships
        message = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).filter(Email.id == message_id).first()
        
        if not message:
            return []
            
        # Build the chain
        chain = []
        
        # Add parent chain in reverse chronological order
        current = message
        while current.parent:
            chain.insert(0, current.parent)
            current = current.parent
            
        # Add the target message
        chain.append(message)
        
        # Add children in chronological order
        chain.extend(sorted(message.children, key=lambda x: x.created_at))
        
        return chain
        
    except Exception as e:
        logger.error(f"Error retrieving message chain for {message_id}: {str(e)}")
        return []
    finally:
        db_session.close()

@messages_bp.route('/messages/<int:message_id>', methods=['GET'])
def get_message(message_id: int):
    """
    Retrieve and display a single message.
    
    Args:
        message_id: ID of the message to display
    """
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
            raw_content=message.content,
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

@messages_bp.route('/messages/<int:message_id>/chain', methods=['GET'])
def view_chain(message_id: int):
    """
    Display the full chain of messages related to a given message ID.
    Shows the parent chain and all child messages in chronological order.
    
    Args:
        message_id: ID of the message to show the chain for
    """
    chain = get_message_chain(message_id)
    
    if not chain:
        return render_template('chain.html', error="Message or chain not found")
    
    # Format timestamps for display
    for message in chain:
        message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
    
    # Return HTML if requested
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'chain.html',
            messages=chain,
            target_id=message_id
        )
    
    # Otherwise return JSON
    return jsonify({
        'chain': [{
            'id': msg.id,
            'subject': msg.subject,
            'content': msg.content,
            'processed_content': msg.processed_content,
            'created_at': msg.created_at.isoformat(),
            'parent_id': msg.parent_id,
            'is_target': msg.id == message_id
        } for msg in chain]
    })

@messages_bp.route('/recent')
def recent_message():
    """Show the most recent message."""
    try:
        db_session = Session()
        message = db_session.query(Email).order_by(Email.created_at.desc()).first()
        
        if not message:
            return render_template('message.html', error="No messages found")
            
        return render_template(
            'message.html',
            message=message,
            created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            raw_content=message.content,
        )
        
    finally:
        db_session.close()

@messages_bp.route('/stream')
def message_stream():
    """Show a stream of recent messages."""
    try:
        db_session = Session()
        messages = db_session.query(Email).options(
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
        db_session.close()
