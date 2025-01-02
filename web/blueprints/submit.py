from flask import Blueprint, request, render_template, url_for, redirect, session, jsonify
from sqlalchemy.orm import joinedload
from typing import Dict, Any, Optional, List, Tuple

from logging_config import get_logger
logger = get_logger(__name__)

from common.database import setup_database
Session, db_success = setup_database()

import common.models
from common.colorscheme import ColorScheme
color_processor = ColorScheme()

from .auth import require_auth

submit_bp = Blueprint('submit', __name__)

@submit_bp.route('/process', methods=['POST'])
@require_auth
def process_message() -> tuple[Dict[str, Any], int]:
    """API endpoint to process and store messages."""
    try:
        data = request.get_json()
        
        if not data or 'subject' not in data or 'content' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        db_session = Session()
        
        user = session['user']
        db_user = common.models.get_or_create_user(db_session, user)

        # Create message object first
        message = common.models.Email(
            subject=data['subject'],
            content=data['content'],
            author=db_user,
            llm_annotations=json.dumps(data.get('llm_annotations', {}))
        )
        
        # Handle message chain if parent_id is provided
        if 'parent_id' in data:
            parent = db_session.query(common.models.Email).get(data['parent_id'])
            if parent:
                message.parent = parent
        
        # Add message to session so it exists before processing content
        db_session.add(message)
        
        # Now process content with access to the message object
        message.processed_content = color_processor.process_content(
            data['content'],
            llm_annotations=data.get('llm_annotations'),
            message=message,
            db_session=db_session
        )
        
        db_session.commit() 
        logger.info(f"Processed message with subject: {data['subject']}")
        
        return jsonify({
            'id': message.id,
            'processed_content': processed_content,
            'view_url': url_for('messages.get_message', message_id=message.id)
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        db_session.close()


@submit_bp.route('/submit', methods=['GET', 'POST'])
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

            db_session = Session()

            user = session['user']
            db_user = common.models.get_or_create_user(db_session, user)

            message = common.models.Email(
                subject=subject,
                content=content,
                author=db_user
            )

            # Handle message chain if parent_id is provided
            if parent_id and parent_id.strip():
                try:
                    parent_id = int(parent_id)
                    parent = db_session.query(common.models.Email).get(parent_id)
                    if parent:
                        message.parent = parent
                    else:
                        logger.warning(f"Parent message {parent_id} not found")
                except ValueError:
                    logger.warning(f"Invalid parent_id format: {parent_id}")

            # Add message to session before processing content
            db_session.add(message)

            # Process content with access to the message object
            message.processed_content = color_processor.process_content(
                content,
                message=message,
                db_session=db_session
            )

            db_session.commit()
            
            view_url = url_for('messages.get_message', message_id=message.id)
            return render_template('submit.html', success=True, view_url=view_url)
            
        except Exception as e:
            logger.error(f"Error processing form submission: {str(e)}")
            return render_template('submit.html', error=str(e))
            
        finally:
            db_session.close()
        # END of processing submission of message by POST
            
    # Get recent messages for the dropdown
    db_session = Session()
    try:
        recent_messages = db_session.query(common.models.Email).order_by(
            common.models.Email.created_at.desc()
        ).limit(50).all()
    except Exception as e:
        logger.error(f"Error fetching recent messages: {str(e)}")
        recent_messages = []
    finally:
        db_session.close()
    return render_template('submit.html', recent_messages=recent_messages)

