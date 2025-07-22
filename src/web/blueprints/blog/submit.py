"""Blueprint for message submission and preview functionality."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.orm import joinedload

import aml_parser
import aml_parser.colorblocks
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from models import get_or_create_user
from models.database import db
from models.models import Email
from web.blueprints.core.errors import handle_error
from web.decorators import navigable, require_auth
from .shared import content_bp

logger = get_logger(__name__)

@content_bp.route('/api/preview', methods=['POST'])
@require_auth
def preview_message():
    """
    Preview handler for message submission.
    
    Processes the content with color tags without storing to database.
    Expects JSON input with 'content' field.
    
    :return: JSON response with rendered HTML
    :raises: HTTP 400 if request is not JSON or missing content
    :raises: HTTP 500 if processing fails
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")
        
    data = request.get_json()
    if not data or 'content' not in data:
        return handle_error("400", "Bad Request", "Content required")
        
    try:
        processed_content = aml_parser.process_message(
            data['content']
        )
        
        return jsonify({
            'processed_content': processed_content
        })
        
    except Exception as e:
        logger.error(f"Error processing preview: {str(e)}")
        return handle_error("500", "Processing Error", "Failed to process message preview", str(e))

@content_bp.route('/submit', methods=['GET'])
@require_auth
@navigable(name="Submit new message", category="main")
def show_submit_form():
    """
    Display the message submission form.
    
    :return: Rendered submit form template
    """
    channel_manager = get_channel_manager()
    
    with db.session() as db_session:
        recent_messages = db_session.query(Email).options(
            joinedload(Email.author)
        ).order_by(
            Email.created_at.desc()
        ).limit(50).all()
        
        return render_template(
            'messages/submit.html',
            recent_messages=recent_messages,
            channels=channel_manager.channels,
            default_channel=channel_manager.default_channel,
            colors=aml_parser.colorblocks.COLORS)

@content_bp.route('/submit', methods=['POST'])
@require_auth
def handle_submit():
    """
    Process message submission from form.
    
    :return: Redirect to new message or error page
    :raises: HTTP 422 if required fields are missing
    """
    channel_manager = get_channel_manager()
    
    subject = request.form.get('subject', '').strip()
    content = request.form.get('content', '').strip()
    channel = request.form.get('channel', channel_manager.default_channel).strip()
    parent_id = request.form.get('parent_id')

    if not subject or not content:
        return handle_error("422", "Validation Error", "Subject and content are required")

    try:
        with db.session() as db_session:
            # Get fresh user object within transaction
            db_user = get_or_create_user(db_session, session['user'])
            
            # Create message
            message = Email(
                subject=subject,
                content=content,
                author=db_user,
                channel=channel
            )

            # Handle message chain if parent_id is provided
            if parent_id and parent_id.strip():
                try:
                    parent_id = int(parent_id)
                    parent = db_session.query(Email).get(parent_id)
                    if parent:
                        message.parent = parent
                    else:
                        logger.warning(f"Parent message {parent_id} not found")
                except ValueError:
                    logger.warning(f"Invalid parent_id format: {parent_id}")

            # Add message to session before processing content
            db_session.add(message)

            # Process content with access to the message object
            message.processed_content = aml_parser.process_message(
                content,
                message=message,
                db_session=db_session
            )
            
            message.preview_content = aml_parser.process_message(
                content,
                message=message,
                db_session=db_session,
                truncated=True
            )
            
            db_session.commit()
            message_id = message.id  # Get ID before session closes
        
        flash('Message submitted successfully!', 'success')
        return redirect(url_for('content.get_message', message_id=message_id))
        
    except Exception as e:
        logger.error(f"Error submitting message: {str(e)}")
        return handle_error("500", "Submission Error", "Failed to submit message", str(e))
