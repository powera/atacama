"""Admin functionality for managing user access to restricted channels."""

import os
from typing import Dict, List

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from sqlalchemy.orm import joinedload

import aml_parser
from aml_parser.lexer import tokenize, TokenType
from aml_parser.parser import parse
from aml_parser.html_generator import generate_html
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.config.domain_config import get_domain_manager
from common.services.archive import get_archive_service
from models import get_or_create_user
from models.database import db
from models.models import Email
from models.users import (
    is_user_admin,
    get_user_by_id,
    grant_channel_access_by_id,
    revoke_channel_access_by_id,
    get_user_channel_access_by_id,
    get_all_users,
)
from models.messages import get_raw_message_by_id
from atacama.blueprints.errors import handle_error
from atacama.decorators import navigable, require_admin, require_auth

logger = get_logger(__name__)

# Get the blog module directory (parent of blueprints/)
blog_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

admin_bp = Blueprint(
    "admin",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)


def is_admin() -> bool:
    """Check if current user has admin access."""
    if not hasattr(g, "user") or not g.user:
        return False
    return is_user_admin(g.user.email)


@admin_bp.route("/admin/users")
@require_auth
@navigable(name="List Users", category="admin")
def list_users() -> ResponseReturnValue:
    """Show list of users and their channel access."""
    if not is_admin():
        flash("Admin access required")
        return redirect(url_for("content.landing_page"))

    with db.session() as db_session:
        # Get all users using the function from models.users
        users = get_all_users(db_session)

        # Get channel access for each user
        user_access = []
        for user in users:
            access = get_user_channel_access_by_id(db_session, user.id)
            user_access.append({"user": user, "access": access})

        # Get admin-controlled channels from configuration
        channel_manager = get_channel_manager()
        admin_channels = [
            name
            for name in channel_manager.get_channel_names()
            if (config := channel_manager.get_channel_config(name)) and config.requires_admin
        ]

        return render_template("admin/users.html", users=user_access, channels=admin_channels)


@admin_bp.route("/admin/users/<int:user_id>/grant", methods=["POST"])
@require_auth
def grant_access(user_id: int) -> ResponseReturnValue:
    """Grant channel access to a user."""
    if not is_admin():
        flash("Admin access required")
        return redirect(url_for("content.landing_page"))

    channel = request.form.get("channel")
    if not channel:
        flash("Channel required")
        return redirect(url_for("admin.list_users"))

    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        flash("Invalid admin-controlled channel")
        return redirect(url_for("admin.list_users"))

    with db.session() as db_session:
        # Update admin channel access using convenience function
        success = grant_channel_access_by_id(db_session, user_id, channel)

        if success:
            db_session.commit()
            # Get user for display purposes only
            user = get_user_by_id(db_session, user_id)
            if user:
                flash(f"Granted {channel} access to {user.email}")
            else:
                flash(f"Granted {channel} access to user {user_id}")
        else:
            flash(f"Failed to grant {channel} access (user not found or invalid channel)")

    return redirect(url_for("admin.list_users"))


@admin_bp.route("/admin/users/<int:user_id>/revoke", methods=["POST"])
@require_auth
def revoke_access(user_id: int) -> ResponseReturnValue:
    """Revoke channel access from a user."""
    if not is_admin():
        flash("Admin access required")
        return redirect(url_for("content.landing_page"))

    channel = request.form.get("channel")
    if not channel:
        flash("Channel required")
        return redirect(url_for("admin.list_users"))

    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        flash("Invalid admin-controlled channel")
        return redirect(url_for("admin.list_users"))

    with db.session() as db_session:
        # Update admin channel access using convenience function
        success = revoke_channel_access_by_id(db_session, user_id, channel)

        if success:
            db_session.commit()
            # Get user for display purposes only
            user = get_user_by_id(db_session, user_id)
            if user:
                flash(f"Revoked {channel} access from {user.email}")
            else:
                flash(f"Revoked {channel} access from user {user_id}")
        else:
            flash(f"Failed to revoke {channel} access (user not found or invalid channel)")

    return redirect(url_for("admin.list_users"))


@admin_bp.route("/admin/messages/<int:message_id>/rechannel", methods=["POST"])
@require_auth
def rechannel_message(message_id: int) -> ResponseReturnValue:
    """Change the channel of a message."""
    if not is_admin():
        flash("Admin access required")
        return redirect(url_for("content.landing_page"))

    new_channel = request.form.get("new_channel")
    if not new_channel:
        flash("New channel is required")
        return redirect(url_for("content.get_message", message_id=message_id))

    new_channel = new_channel.lower()
    channel_config = get_channel_manager().get_channel_config(new_channel)
    if not channel_config:
        flash("Invalid channel")
        return redirect(url_for("content.get_message", message_id=message_id))

    with db.session() as db_session:
        message = get_raw_message_by_id(db_session, message_id)

        if not message:
            flash("Message not found")
            return redirect(url_for("content.landing_page"))

        old_channel = message.channel
        message.channel = new_channel

        db_session.commit()
        flash(f"Message re-channeled from {old_channel} to {new_channel}")

    return redirect(url_for("content.get_message", message_id=message_id))


# =============================================================================
# Message Submission (Admin-only)
# =============================================================================


@admin_bp.route("/admin/api/preview", methods=["POST"])
@require_admin
def preview_message() -> ResponseReturnValue:
    """
    Preview handler for message submission (admin only).

    Processes the content with color tags without storing to database.
    Expects JSON input with 'content' field.

    :return: JSON response with rendered HTML
    :raises: HTTP 400 if request is not JSON or missing content
    :raises: HTTP 500 if processing fails
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json()
    if not data or "content" not in data:
        return handle_error("400", "Bad Request", "Content required")

    try:
        processed_content = aml_parser.process_message(data["content"])

        return jsonify({"processed_content": processed_content})

    except Exception as e:
        logger.error(f"Error processing preview: {str(e)}")
        return handle_error("500", "Processing Error", "Failed to process message preview", str(e))


@admin_bp.route("/admin/submit", methods=["GET"])
@require_admin
@navigable(name="Write post", category="admin")
def show_submit_form() -> ResponseReturnValue:
    """
    Display the message submission form (admin only).

    :return: Rendered submit form template
    """
    channel_manager = get_channel_manager()

    with db.session() as db_session:
        recent_messages = (
            db_session.query(Email)
            .options(joinedload(Email.author))
            .order_by(Email.created_at.desc())
            .limit(50)
            .all()
        )

        return render_template(
            "messages/submit.html",
            recent_messages=recent_messages,
            channels=channel_manager.channels,
            default_channel=channel_manager.default_channel,
            colors=aml_parser.colorblocks.COLORS,
        )


@admin_bp.route("/admin/submit", methods=["POST"])
@require_admin
def handle_submit() -> ResponseReturnValue:
    """
    Process message submission from form (admin only).

    :return: Redirect to new message or error page
    :raises: HTTP 422 if required fields are missing
    """
    channel_manager = get_channel_manager()

    subject = request.form.get("subject", "").strip()
    content = request.form.get("content", "").strip()
    channel = request.form.get("channel", channel_manager.default_channel).strip()
    parent_id = request.form.get("parent_id")

    if not subject or not content:
        return handle_error("422", "Validation Error", "Subject and content are required")

    try:
        with db.session() as db_session:
            # Get fresh user object within transaction
            db_user = get_or_create_user(db_session, session["user"])

            # Create message
            message = Email(subject=subject, content=content, author=db_user, channel=channel)

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

            # Process content with access to the message object and extract URLs
            tokens = list(tokenize(content))
            ast = parse(iter(tokens))

            # Extract URLs from tokens
            extracted_urls = []
            for token in tokens:
                if token.type == TokenType.URL:
                    extracted_urls.append(token.value)

            # Generate HTML content
            message.processed_content = generate_html(ast, message=message, db_session=db_session)

            message.preview_content = generate_html(
                ast, message=message, db_session=db_session, truncated=True
            )

            db_session.commit()
            message_id = message.id  # Get ID before session closes
            # Note: processed_content and extracted_urls are already available from above

        # Archive URLs and posts if archive service is enabled
        archive_service = get_archive_service()
        if archive_service:
            try:
                # Archive URLs from the message content in a separate thread to avoid blocking
                import threading

                def archive_content():
                    try:
                        # 1. Always archive URLs found in message content (in production)
                        archived_url_count = archive_service.archive_urls_from_content(
                            urls=extracted_urls
                        )
                        if archived_url_count > 0:
                            logger.info(
                                f"Archived {archived_url_count} URLs from message {message_id} content"
                            )

                        # 2. Archive the post itself if any domain with archiving supports this channel
                        domain_manager = get_domain_manager()
                        archiving_domains = []

                        for domain_key, domain_config in domain_manager.domains.items():
                            if (
                                domain_config.auto_archive_enabled
                                and domain_config.channel_allowed(channel)
                            ):
                                archiving_domains.append(domain_config)

                        if archiving_domains:
                            # Generate the message URL for archiving the post itself
                            message_url = url_for(
                                "content.get_message", message_id=message_id, _external=True
                            )

                            # Use the first archiving domain to avoid duplicate submissions
                            domain_config = archiving_domains[0]
                            archived_post_count = archive_service.archive_message_post(
                                message_url, domain_config
                            )
                            if archived_post_count > 0:
                                domain_names = [d.name for d in archiving_domains]
                                logger.info(
                                    f"Archived message post {message_id} for domains: {', '.join(domain_names)}"
                                )
                        else:
                            logger.debug(
                                f"No domains with archiving enabled support channel {channel}"
                            )

                    except Exception as e:
                        logger.error(f"Error archiving content for message {message_id}: {e}")

                # Start archiving in background thread
                archive_thread = threading.Thread(target=archive_content, daemon=True)
                archive_thread.start()
            except Exception as e:
                logger.error(f"Error starting archive thread for message {message_id}: {e}")

        flash("Message submitted successfully!", "success")
        return redirect(url_for("content.get_message", message_id=message_id))

    except Exception as e:
        logger.error(f"Error submitting message: {str(e)}")
        return handle_error("500", "Submission Error", "Failed to submit message", str(e))
