"""Error handling blueprint and utilities for Atacama."""

from flask import Blueprint, render_template, request, jsonify, current_app, g, session
from flask.typing import ResponseReturnValue
from sqlalchemy.exc import SQLAlchemyError

from common.config.channel_config import get_channel_manager
from common.config.domain_config import get_domain_manager
from common.base.logging_config import get_logger
from models.database import db
from models import get_or_create_user

logger = get_logger(__name__)

errors_bp = Blueprint('errors', __name__)


def _ensure_domain_context() -> None:
    """
    Ensure domain/theme context is set up for error pages.

    For 404 errors, Flask's before_request handler doesn't run because there's
    no matching route. This function ensures the domain and theme are detected
    from the request host so error pages use the correct layout.
    """
    # Skip if already set (e.g., from before_request handler for non-404 errors)
    if hasattr(g, 'theme_layout') and g.theme_layout:
        return

    try:
        domain_manager = get_domain_manager()
        host = request.host

        # Detect domain from host
        domain_key = domain_manager.get_domain_for_host(host)
        domain_config = domain_manager.get_domain_config(domain_key)

        # Get theme configuration
        theme_key = domain_config.theme
        theme_config = domain_manager.get_theme_config(theme_key)

        # Set values in Flask's g object for the context processor
        g.current_domain = domain_key
        g.domain_config = domain_config
        g.theme_config = theme_config
        g.theme_css_files = theme_config.css_files
        g.theme_layout = theme_config.layout
    except Exception as e:
        logger.warning(f"Failed to detect domain for error page: {e}")
        # Fall back to defaults - context processor will handle missing values


def handle_error(error_code: str, error_title: str, error_message: str, details: str | None = None) -> ResponseReturnValue:
    """
    Unified error handler that returns HTML or JSON based on Accept header.

    :param error_code: HTTP status code as string
    :param error_title: Title for the error page
    :param error_message: User-friendly error description
    :param details: Optional technical details (shown only in debug mode)
    :return: HTML template or JSON response with appropriate status code
    """
    status_code = int(error_code)

    # Ensure domain/theme context is set up (may not be for 404 errors)
    _ensure_domain_context()

    # Ensure user session is populated if available
    if 'user' in session and not hasattr(g, 'user'):
        try:
            with db.session() as db_session:
                db_session.expire_on_commit = False
                g.user = get_or_create_user(db_session, session['user'])
        except SQLAlchemyError as e:
            logger.error(f"Database error during error handling: {str(e)}")
            g.user = None
    
    # Get channel info for error page context
    channel_manager = get_channel_manager()
    try:
        public_channels = channel_manager.get_public_channels()
    except Exception as e:
        logger.error(f"Error fetching channels during error handling: {str(e)}")
        public_channels = []
    
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'error.html',
            error_code=error_code,
            error_title=error_title,
            error_message=error_message,
            technical_details=details if current_app.debug else None,
            public_channels=public_channels,
            channel_manager=channel_manager
        ), status_code
    
    response = {
        'error': error_title.lower().replace(' ', '_'),
        'message': error_message
    }
    if current_app.debug and details:
        response['details'] = details
    
    return jsonify(response), status_code

@errors_bp.app_errorhandler(400)
def bad_request(e: Exception) -> ResponseReturnValue:
    """Handle 400 Bad Request errors."""
    logger.warning(f"Bad request: {str(e)}")
    return handle_error(
        "400",
        "Bad Request",
        "The request could not be understood by the server due to malformed syntax.",
        str(e)
    )

@errors_bp.app_errorhandler(401)
def unauthorized(e: Exception) -> ResponseReturnValue:
    """Handle 401 Unauthorized errors."""
    logger.info(f"Unauthorized access attempt: {str(e)}")
    return handle_error(
        "401",
        "Unauthorized",
        "Authentication is required to access this resource.",
        str(e)
    )

@errors_bp.app_errorhandler(403)
def forbidden(e: Exception) -> ResponseReturnValue:
    """Handle 403 Forbidden errors."""
    logger.warning(f"Forbidden access attempt: {str(e)}")
    return handle_error(
        "403",
        "Forbidden",
        "You don't have permission to access this resource.",
        str(e)
    )

@errors_bp.app_errorhandler(404)
def page_not_found(e: Exception) -> ResponseReturnValue:
    """Handle 404 Not Found errors."""
    logger.info(f"Page not found: {request.path}")
    return handle_error(
        "404",
        "Page Not Found",
        "The page you are looking for could not be found. It might have been removed, renamed, or does not exist.",
        str(e)
    )

@errors_bp.app_errorhandler(405)
def method_not_allowed(e: Exception) -> ResponseReturnValue:
    """Handle 405 Method Not Allowed errors."""
    logger.warning(f"Method not allowed: {request.method} {request.path}")
    return handle_error(
        "405",
        "Method Not Allowed",
        f"The {request.method} method is not allowed for this endpoint.",
        str(e)
    )

@errors_bp.app_errorhandler(500)
def internal_server_error(e: Exception) -> ResponseReturnValue:
    """Handle 500 Internal Server errors."""
    logger.error(f"Internal server error: {str(e)}", exc_info=True)
    return handle_error(
        "500",
        "Internal Server Error",
        "An unexpected error occurred. Our team has been notified and is working to resolve the issue.",
        str(e)
    )

@errors_bp.app_errorhandler(SQLAlchemyError)
def handle_database_error(e: SQLAlchemyError) -> ResponseReturnValue:
    """Handle SQLAlchemy database errors."""
    logger.error(f"Database error: {str(e)}", exc_info=True)
    return handle_error(
        "500",
        "Database Error",
        "A database error occurred. Our team has been notified and is working to resolve the issue.",
        str(e)
    )
