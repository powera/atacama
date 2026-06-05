"""Shared blueprints and helpers for blog functionality."""

import os
import threading

from flask import Blueprint, url_for

from aml_parser.lexer import tokenize, TokenType
from aml_parser.parser import parse
from aml_parser.html_generator import generate_html
from common.base.logging_config import get_logger
from common.config.domain_config import get_domain_manager
from common.services.archive import get_archive_service
from models.models import Email

logger = get_logger(__name__)

# Get the blog module directory (parent of blueprints/)
blog_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Main content blueprint - handles content display, submission, and articles
content_bp = Blueprint(
    "content",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)

# Specialized blueprints for distinct functionality
quotes_bp = Blueprint(
    "quotes",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
feeds_bp = Blueprint(
    "feeds",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
statistics_bp = Blueprint(
    "statistics",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
widgets_bp = Blueprint(
    "widgets",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)


def create_email_message(db_session, *, author, subject, content, channel, parent_id=None):
    """
    Create and persist an :class:`Email` message from raw AML content.

    Runs the shared tokenize -> parse -> generate_html pipeline used by both the
    admin form submit route and the JSON API. The caller owns the surrounding
    ``db.session()``; this function adds and processes the message but does not
    commit.

    :param db_session: Active SQLAlchemy session
    :param author: User model instance to set as the message author
    :param subject: Message subject/title
    :param content: Raw AML markup
    :param channel: Channel name to post into
    :param parent_id: Optional parent message id for threaded chains. Invalid or
                      unknown ids are logged and ignored.
    :return: Tuple of (message, extracted_urls)
    """
    message = Email(subject=subject, content=content, author=author, channel=channel)

    # Handle message chain if parent_id is provided
    if parent_id is not None and str(parent_id).strip():
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

    # Process content with access to the message object and extract URLs
    tokens = list(tokenize(content))
    ast = parse(iter(tokens))

    extracted_urls = [token.value for token in tokens if token.type == TokenType.URL]

    message.processed_content = generate_html(ast, message=message, db_session=db_session)
    message.preview_content = generate_html(
        ast, message=message, db_session=db_session, truncated=True
    )

    return message, extracted_urls


def start_archive_thread(message_id, extracted_urls, channel):
    """
    Kick off background archiving for a newly created message, if archiving is
    enabled. Archives both URLs found in the content and (for domains configured
    with auto-archiving) the message post itself. Never raises.

    :param message_id: ID of the persisted message
    :param extracted_urls: URLs extracted from the message content
    :param channel: Channel the message was posted to
    """
    archive_service = get_archive_service()
    if not archive_service:
        return

    def archive_content():
        try:
            # 1. Always archive URLs found in message content (in production)
            archived_url_count = archive_service.archive_urls_from_content(urls=extracted_urls)
            if archived_url_count > 0:
                logger.info(f"Archived {archived_url_count} URLs from message {message_id} content")

            # 2. Archive the post itself if any domain with archiving supports this channel
            domain_manager = get_domain_manager()
            archiving_domains = [
                domain_config
                for domain_config in domain_manager.domains.values()
                if domain_config.auto_archive_enabled and domain_config.channel_allowed(channel)
            ]

            if archiving_domains:
                message_url = url_for("content.get_message", message_id=message_id, _external=True)
                # Use the first archiving domain to avoid duplicate submissions
                archived_post_count = archive_service.archive_message_post(
                    message_url, archiving_domains[0]
                )
                if archived_post_count > 0:
                    domain_names = [d.name for d in archiving_domains]
                    logger.info(
                        f"Archived message post {message_id} for domains: {', '.join(domain_names)}"
                    )
            else:
                logger.debug(f"No domains with archiving enabled support channel {channel}")

        except Exception as e:
            logger.error(f"Error archiving content for message {message_id}: {e}")

    try:
        archive_thread = threading.Thread(target=archive_content, daemon=True)
        archive_thread.start()
    except Exception as e:
        logger.error(f"Error starting archive thread for message {message_id}: {e}")
