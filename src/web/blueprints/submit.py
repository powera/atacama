from flask import Blueprint, request, render_template, url_for, redirect, session, jsonify
from sqlalchemy.orm import joinedload
from typing import Dict, Any, Optional, List, Tuple

from common.auth import require_auth
from common.channel_config import get_channel_manager
from common.logging_config import get_logger
logger = get_logger(__name__)

from common.database import db

import common.models
from common.colorscheme import ColorScheme
color_processor = ColorScheme()

submit_bp = Blueprint('submit', __name__)

@submit_bp.route('/api/preview', methods=['POST'])
@require_auth
def preview_message():
    """
    Preview handler for message submission.
    Processes the content with color tags without storing to database.
    Expects JSON input with 'content' field.
    Returns JSON with processed HTML content.
    
    :return: JSON response with rendered HTML
    """
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
        
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Content required'}), 400
        
    try:
        processed_content = color_processor.process_content(
            data['content'],
            message=None,  # Skip database operations
            db_session=None
        )
        
        return jsonify({
            'processed_content': processed_content
        })
        
    except Exception as e:
        logger.error(f"Error processing preview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@submit_bp.route('/submit', methods=['GET', 'POST'])
@require_auth
def submit_form():
    """Handle message submission via HTML form."""
    if request.method == 'POST':
        with db.session() as db_session:
            subject = request.form.get('subject', '')
            content = request.form.get('content', '')
            parent_id = request.form.get('parent_id')

            if not subject or not content:
                return render_template('error.html', error_code=422), 422

            user = session['user']
            db_user = common.models.get_or_create_user(db_session, user)
            message = common.models.Email(
                subject=subject,
                content=content,
                author=db_user,
                channel=request.form.get('channel', 'private')
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
            
    else:  # method=GET
        # Get recent messages for the dropdown
        with db.session() as db_session:
            recent_messages = db_session.query(common.models.Email).order_by(
                common.models.Email.created_at.desc()
            ).limit(50).all()
            return render_template(
                'submit.html',
                recent_messages=recent_messages,
                colors=color_processor.COLORS,
                channels=get_channel_manager().channels)

