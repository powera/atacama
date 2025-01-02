from flask import Blueprint, render_template, request, jsonify, current_app
from logging_config import get_logger

logger = get_logger(__name__)

errors_bp = Blueprint('errors', __name__)

@errors_bp.app_errorhandler(404)
def page_not_found(e):
    """Handle 404 errors by returning a custom error page."""
    # Check if the request accepts HTML
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'error.html',
            error_code="404",
            error_title="Page Not Found",
            error_message="The page you are looking for could not be found. It might have been removed, renamed, or does not exist."
        ), 404
    
    # Return JSON for API requests
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found'
    }), 404

@errors_bp.app_errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors by returning a custom error page."""
    logger.error(f"Internal server error: {str(e)}")
    
    # Check if the request accepts HTML
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'error.html',
            error_code="500",
            error_title="Internal Server Error",
            error_message="An unexpected error occurred. Our team has been notified and is working to resolve the issue.",
            technical_details=str(e) if current_app.debug else None
        ), 500
    
    # Return JSON for API requests
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500
