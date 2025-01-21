"""Blueprint for message submission and preview functionality."""

from flask import Blueprint, request, render_template, url_for, redirect, session
from flask import jsonify, g, flash
from sqlalchemy.orm import joinedload

from common.auth import require_auth
from common.channel_config import get_channel_manager
from common.colorscheme import ColorScheme
from common.database import db
from common.logging_config import get_logger
from common.models import Email, get_or_create_user

logger = get_logger(__name__)
color_processor = ColorScheme()
submit_bp = Blueprint('submit', __name__)

@submit_bp.route('/api/preview', methods=['POST'])
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

@submit_bp.route('/submit', methods=['GET'])
@require_auth
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
            'submit.html',
            recent_messages=recent_messages,
            colors=color_processor.COLORS,
            channels=channel_manager.channels,
            default_channel=channel_manager.default_channel)

@submit_bp.route('/submit', methods=['POST'])
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
        return render_template('error.html', error_code=422), 422

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
        message.processed_content = color_processor.process_content(
            content,
            message=message,
            db_session=db_session
        )

        db_session.commit()
        message_id = message.id  # Get ID before session closes
    
    flash('Message submitted successfully!', 'success')
    return redirect(url_for('content.get_message', message_id=message_id))
