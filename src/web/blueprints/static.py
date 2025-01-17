"""Blueprint for serving static assets."""

import os
from typing import Any

from flask import Blueprint, send_from_directory, Response

import constants
from common.logging_config import get_logger

logger = get_logger(__name__)

static_bp = Blueprint('static', __name__)

@static_bp.route('/js/<path:filename>')
def serve_js(filename: str) -> Response:
    """
    Serve JavaScript files from the js directory.
    
    :param filename: Name of the JS file to serve
    :return: JS file response
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        js_dir = os.path.join(constants.WEB_DIR, 'js')
        return send_from_directory(js_dir, filename)
    except Exception as e:
        logger.error(f"Error serving JS file {filename}: {str(e)}")
        raise

@static_bp.route('/css/<path:filename>')
def serve_css(filename: str) -> Response:
    """
    Serve CSS files from the css directory.
    
    :param filename: Name of the CSS file to serve
    :return: CSS file response
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        css_dir = os.path.join(constants.WEB_DIR, 'css')
        return send_from_directory(css_dir, filename)
    except Exception as e:
        logger.error(f"Error serving CSS file {filename}: {str(e)}")
        raise

@static_bp.route('/favicon.ico')
def serve_favicon() -> Response:
    """
    Serve the favicon.ico file from the static directory.
    
    :return: Favicon file response
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        return send_from_directory(constants.STATIC_DIR, 'favicon_multisize.ico')
    except Exception as e:
        logger.error(f"Error serving favicon: {str(e)}")
        raise

@static_bp.route('/apple-touch-icon.png')
def serve_touch_icon() -> Response:
    """
    Serve the apple-touch-icon.png file from the static directory.
    
    :return: Apple touch icon file response
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        return send_from_directory(constants.STATIC_DIR, 'apple-touch-icon.png')
    except Exception as e:
        logger.error(f"Error serving touch icon: {str(e)}")
        raise

@static_bp.route('/robots.txt')
def serve_robots_txt() -> Response:
    """
    Serve the robots.txt file from the static directory.
    
    :return: Robots.txt file response 
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        return send_from_directory(constants.STATIC_DIR, 'robots.txt')
    except Exception as e:
        logger.error(f"Error serving robots.txt: {str(e)}")
        raise
