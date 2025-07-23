"""Blueprint for serving static assets."""

import os
from typing import Any

from flask import Blueprint, send_from_directory, send_file, Response

import constants
from common.base.logging_config import get_logger

logger = get_logger(__name__)

static_bp = Blueprint('static', __name__)


@static_bp.route("/trakaido")
@static_bp.route("/trakaido/")
def trakaido_index() -> Response:
    """Serve the Trakaido single-page application."""
    TRAKAIDO_PATH_PROD = "/home/atacama/trakaido_react/build/index.html"
    if os.path.exists(TRAKAIDO_PATH_PROD):
        # In production, serve the compiled index.html from the Trakaido repo
        return send_file(TRAKAIDO_PATH_PROD)
    return send_file(constants.WEB_DIR + "/static/trakaido.html")

@static_bp.route('/js/<path:filename>')
def serve_js(filename: str) -> Response:
    """
    Serve JavaScript files from the js directory.
    
    :param filename: Name of the JS file to serve
    :return: JS file response with 1-hour cache headers
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        js_dir = os.path.join(constants.WEB_DIR, 'js')
        response = send_from_directory(js_dir, filename)
        # Set cache headers for 1 hour (3600 seconds)
        response.cache_control.max_age = 3600
        response.cache_control.public = True
        return response
    except Exception as e:
        logger.error(f"Error serving JS file {filename}: {str(e)}")
        raise

@static_bp.route('/css/<path:filename>')
def serve_css(filename: str) -> Response:
    """
    Serve CSS files from the css directory.
    
    :param filename: Name of the CSS file to serve
    :return: CSS file response with 1-hour cache headers
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        css_dir = os.path.join(constants.WEB_DIR, 'css')
        response = send_from_directory(css_dir, filename)
        # Set cache headers for 1 hour (3600 seconds)
        response.cache_control.max_age = 3600
        response.cache_control.public = True
        return response
    except Exception as e:
        logger.error(f"Error serving CSS file {filename}: {str(e)}")
        raise

@static_bp.route('/favicon.ico')
def serve_favicon() -> Response:
    """
    Serve the favicon.ico file from the static directory.
    
    :return: Favicon file response with 1-hour cache headers
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        response = send_from_directory(constants.STATIC_DIR, 'favicon_multisize.ico')
        # Set cache headers for 1 hour (3600 seconds)
        response.cache_control.max_age = 3600
        response.cache_control.public = True
        return response
    except Exception as e:
        logger.error(f"Error serving favicon: {str(e)}")
        raise

@static_bp.route('/apple-touch-icon.png')
@static_bp.route('/apple-touch-icon-precomposed.png')
def serve_touch_icon() -> Response:
    """
    Serve the apple-touch-icon.png file from the static directory.
    
    :return: Apple touch icon file response
    :raises: werkzeug.exceptions.NotFound if file doesn't exist
    """
    try:
        response = send_from_directory(constants.STATIC_DIR, 'apple-touch-icon.png')
        # Set cache headers for 1 hour (3600 seconds)
        response.cache_control.max_age = 3600
        response.cache_control.public = True
        return response
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
