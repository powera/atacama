from flask import Blueprint, render_template, request, jsonify, current_app
from logging_config import get_logger

logger = get_logger(__name__)

errors_bp = Blueprint('errors', __name__)

def handle_error(error_code, error_title, error_message, details=None):
    """Unified error handler that returns HTML or JSON based on Accept header.
    
    :param error_code: HTTP status code as string
    :param error_title: Title for the error page
    :param error_message: User-friendly error description
    :param details: Optional technical details (shown only in debug mode)
    :return: HTML template or JSON response with appropriate status code
    """
    status_code = int(error_code)
    
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'error.html',
            error_code=error_code,
            error_title=error_title,
            error_message=error_message,
            technical_details=details if current_app.debug else None
        ), status_code
    
    response = {
        'error': error_title.lower(),
        'message': error_message
    }
    if current_app.debug and details:
        response['details'] = details
    
    return jsonify(response), status_code

@errors_bp.app_errorhandler(400)
def bad_request(e):
    """Handle 400 Bad Request errors."""
    return handle_error(
        "400",
        "Bad Request",
        "The request could not be understood by the server due to malformed syntax.",
        str(e)
    )

@errors_bp.app_errorhandler(401)
def unauthorized(e):
    """Handle 401 Unauthorized errors."""
    return handle_error(
        "401",
        "Unauthorized",
        "Authentication is required to access this resource.",
        str(e)
    )

@errors_bp.app_errorhandler(403)
def forbidden(e):
    """Handle 403 Forbidden errors."""
    return handle_error(
        "403",
        "Forbidden",
        "You don't have permission to access this resource.",
        str(e)
    )

@errors_bp.app_errorhandler(404)
def page_not_found(e):
    """Handle 404 Not Found errors."""
    return handle_error(
        "404",
        "Page Not Found",
        "The page you are looking for could not be found. It might have been removed, renamed, or does not exist.",
        str(e)
    )

@errors_bp.app_errorhandler(405)
def method_not_allowed(e):
    """Handle 405 Method Not Allowed errors."""
    return handle_error(
        "405",
        "Method Not Allowed",
        f"The {request.method} method is not allowed for this endpoint.",
        str(e)
    )

@errors_bp.app_errorhandler(500)
def internal_server_error(e):
    """Handle 500 Internal Server errors."""
    logger.error(f"Internal server error: {str(e)}")
    return handle_error(
        "500",
        "Internal Server Error",
        "An unexpected error occurred. Our team has been notified and is working to resolve the issue.",
        str(e)
    )
