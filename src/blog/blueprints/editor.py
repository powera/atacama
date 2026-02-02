"""Blueprint for the three-stage blog post editor.

This blueprint provides endpoints for composing blog posts incrementally
with LLM assistance and public/private version support.
"""

import uuid

from flask import jsonify, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from sqlalchemy.orm import joinedload

import aml_parser
from aml_parser.lexer import tokenize
from aml_parser.parser import parse
from aml_parser.html_generator import generate_html
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.llm.editor_assistant import EditorAssistant
from models import get_or_create_user
from models.database import db
from models.models import Email
from atacama.blueprints.errors import handle_error
from atacama.decorators import navigable, require_auth
from blog.blueprints.shared import content_bp

logger = get_logger(__name__)

# Initialize editor assistant
editor_assistant = EditorAssistant()


@content_bp.route('/editor/new', methods=['GET'])
@require_auth
@navigable(name="Three-Stage Editor", category="main")
def editor_new() -> ResponseReturnValue:
    """
    Create a new draft and redirect to the editor.

    Generates a new draft ID (UUID) and redirects to the editor page.
    Drafts are stored client-side in localStorage until published.

    :return: Redirect to editor page
    """
    draft_id = str(uuid.uuid4())
    return redirect(url_for('content.editor_draft', draft_id=draft_id))


@content_bp.route('/editor/<draft_id>', methods=['GET'])
@require_auth
def editor_draft(draft_id: str) -> ResponseReturnValue:
    """
    Display the three-stage editor for a draft.

    The draft content is stored in localStorage on the client side.
    This endpoint just serves the editor UI.

    :param draft_id: UUID of the draft
    :return: Rendered editor template
    """
    channel_manager = get_channel_manager()

    with db.session() as db_session:
        recent_messages = db_session.query(Email).options(
            joinedload(Email.author)
        ).order_by(
            Email.created_at.desc()
        ).limit(50).all()

        return render_template(
            'editor/three_stage.html',
            draft_id=draft_id,
            channels=channel_manager.channels,
            default_channel=channel_manager.default_channel,
            recent_messages=recent_messages,
            colors=aml_parser.colorblocks.COLORS
        )


@content_bp.route('/api/editor/<draft_id>/ai-append', methods=['POST'])
@require_auth
def editor_ai_append(draft_id: str) -> ResponseReturnValue:
    """
    AI generates new content based on user input, concatenated to existing.
    Preserves existing content exactly (including ---- dividers).

    Request JSON:
        - input: What to write about
        - current_content: The current AML content
        - target_version: "both" or "private"
        - model: "gpt-5-nano" or "gpt-5-mini"

    :param draft_id: UUID of the draft
    :return: JSON response with new_content
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    if not data or 'input' not in data:
        return handle_error("400", "Bad Request", "Input required")

    user_input = data.get('input', '').strip()
    current_content = data.get('current_content', '')
    target_version = data.get('target_version', 'both')
    model = data.get('model', 'gpt-5-nano')

    if not user_input:
        return handle_error("400", "Bad Request", "Input cannot be empty")

    if target_version not in ('both', 'private'):
        target_version = 'both'
    if model not in ('gpt-5-nano', 'gpt-5-mini'):
        model = 'gpt-5-nano'

    try:
        result = editor_assistant.ai_append(
            user_input=user_input,
            current_content=current_content,
            target_version=target_version,
            model=model
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in AI append: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'new_content': current_content
        })


@content_bp.route('/api/editor/<draft_id>/ai-command', methods=['POST'])
@require_auth
def editor_ai_command(draft_id: str) -> ResponseReturnValue:
    """
    AI executes a command that may modify/delete/restructure content.
    Returns full rewritten content.

    Request JSON:
        - input: The command (e.g., "delete last paragraph")
        - current_content: The current AML content
        - target_version: "both" or "private"
        - model: "gpt-5-nano" or "gpt-5-mini"

    :param draft_id: UUID of the draft
    :return: JSON response with new_content
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    if not data or 'input' not in data:
        return handle_error("400", "Bad Request", "Input required")

    user_input = data.get('input', '').strip()
    current_content = data.get('current_content', '')
    target_version = data.get('target_version', 'both')
    model = data.get('model', 'gpt-5-nano')

    if not user_input:
        return handle_error("400", "Bad Request", "Input cannot be empty")

    if target_version not in ('both', 'private'):
        target_version = 'both'
    if model not in ('gpt-5-nano', 'gpt-5-mini'):
        model = 'gpt-5-nano'

    try:
        result = editor_assistant.ai_command(
            user_input=user_input,
            current_content=current_content,
            target_version=target_version,
            model=model
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in AI command: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'new_content': current_content
        })


@content_bp.route('/api/editor/<draft_id>/quick-append', methods=['POST'])
@require_auth
def editor_quick_append(draft_id: str) -> ResponseReturnValue:
    """
    Quick append content without LLM processing.

    This is a faster path for when the user just wants to add literal text
    without any LLM interpretation or formatting suggestions.

    Request JSON:
        - input: The text to append
        - current_content: The current AML content
        - target_version: "both" or "private"

    :param draft_id: UUID of the draft
    :return: JSON response with updated content
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    if not data or 'input' not in data:
        return handle_error("400", "Bad Request", "Input required")

    user_input = data.get('input', '').strip()
    current_content = data.get('current_content', '')
    target_version = data.get('target_version', 'both')

    if not user_input:
        return handle_error("400", "Bad Request", "Input cannot be empty")

    try:
        result = editor_assistant.quick_append(
            user_input=user_input,
            current_content=current_content,
            target_version=target_version
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in quick append: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'new_content': current_content
        })


@content_bp.route('/api/editor/<draft_id>/preview', methods=['POST'])
@require_auth
def editor_preview(draft_id: str) -> ResponseReturnValue:
    """
    Generate rendered HTML preview of the draft content.

    Request JSON:
        - content: The AML content to render
        - version: "private" (full content) or "public" (with private markers stripped)

    Response JSON:
        - success: bool
        - html: The rendered HTML
        - error: Error message if success is False

    :param draft_id: UUID of the draft
    :return: JSON response with rendered HTML
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    content = data.get('content', '')
    version = data.get('version', 'private')

    try:
        # Extract public content if requested
        if version == 'public':
            content = aml_parser.extract_public_content(content)

        # Process the AML content
        if content:
            html = aml_parser.process_message(content)
        else:
            html = '<p class="empty-content">No content yet</p>'

        return jsonify({
            'success': True,
            'html': html,
            'error': None
        })

    except Exception as e:
        logger.error(f"Error generating preview: {str(e)}")
        return jsonify({
            'success': False,
            'html': f'<p class="error">Error generating preview: {str(e)}</p>',
            'error': str(e)
        })


@content_bp.route('/api/editor/<draft_id>/publish', methods=['POST'])
@require_auth
def editor_publish(draft_id: str) -> ResponseReturnValue:
    """
    Publish the draft as a new Email message.

    Creates both the private (full) and public (markers stripped) versions.

    Request JSON:
        - subject: The message subject
        - content: The full AML content (including private markers)
        - channel: The channel to publish to
        - parent_id: Optional parent message ID for chains

    Response JSON:
        - success: bool
        - message_id: The ID of the created message
        - message_url: URL to view the message
        - error: Error message if success is False

    :param draft_id: UUID of the draft
    :return: JSON response with publish result
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    subject = data.get('subject', '').strip()
    content = data.get('content', '').strip()
    channel = data.get('channel', get_channel_manager().default_channel).strip()
    parent_id = data.get('parent_id')

    if not subject:
        return jsonify({
            'success': False,
            'error': 'Subject is required'
        })

    if not content:
        return jsonify({
            'success': False,
            'error': 'Content is required'
        })

    try:
        with db.session() as db_session:
            # Get fresh user object within transaction
            db_user = get_or_create_user(db_session, session['user'])

            # Create message with full (private) content
            message = Email(
                subject=subject,
                content=content,
                author=db_user,
                channel=channel
            )

            # Handle message chain if parent_id is provided
            if parent_id:
                try:
                    parent_id = int(parent_id)
                    parent = db_session.query(Email).get(parent_id)
                    if parent:
                        message.parent = parent
                    else:
                        logger.warning(f"Parent message {parent_id} not found")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid parent_id format: {parent_id}")

            # Add message to session before processing content
            db_session.add(message)

            # Process full (private) content
            tokens = list(tokenize(content))
            ast = parse(iter(tokens))

            message.processed_content = generate_html(
                ast,
                message=message,
                db_session=db_session
            )

            message.preview_content = generate_html(
                ast,
                message=message,
                db_session=db_session,
                truncated=True
            )

            # Generate public version (with private markers stripped)
            public_content = aml_parser.extract_public_content(content)
            if public_content and public_content != content:
                message.public_content = public_content

                # Process public content for rendering
                public_tokens = list(tokenize(public_content))
                public_ast = parse(iter(public_tokens))
                message.public_processed_content = generate_html(
                    public_ast,
                    message=message,
                    db_session=db_session
                )
            else:
                # No private content, public version is same as private
                message.public_content = None
                message.public_processed_content = None

            db_session.commit()
            message_id = message.id

        return jsonify({
            'success': True,
            'message_id': message_id,
            'message_url': url_for('content.get_message', message_id=message_id),
            'error': None
        })

    except Exception as e:
        logger.error(f"Error publishing draft: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message_id': None,
            'message_url': None
        })


@content_bp.route('/api/editor/check-private', methods=['POST'])
@require_auth
def editor_check_private() -> ResponseReturnValue:
    """
    Check if content contains private markers.

    Request JSON:
        - content: The AML content to check

    Response JSON:
        - has_private: bool indicating if private markers exist

    :return: JSON response
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    content = data.get('content', '')

    return jsonify({
        'has_private': aml_parser.has_private_content(content)
    })
