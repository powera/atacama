from flask import Blueprint, send_from_directory
import os

from common.logging_config import get_logger
logger = get_logger(__name__)

import constants

static_bp = Blueprint('static', __name__)
@static_bp.route('/js/<path:filename>')
def serve_js(filename: str):
    """
    Serve JS files from the js directory.

    :param filename: Name of the JS file to serve
    :return: JS file response
    """
    js_dir = os.path.join(constants.WEB_DIR, 'js')
    return send_from_directory(js_dir, filename)

@static_bp.route('/css/<path:filename>')
def serve_css(filename: str):
    """
    Serve CSS files from the css directory.

    :param filename: Name of the CSS file to serve
    :return: CSS file response
    """
    css_dir = os.path.join(constants.WEB_DIR, 'css')
    return send_from_directory(css_dir, filename)

@static_bp.route('/favicon.ico')
def serve_favicon():
    """
    Serve the favicon.ico file from the static directory.
    
    :return: Favicon file response
    """
    return send_from_directory(constants.STATIC_DIR, 'favicon_multisize.ico')

@static_bp.route('/apple-touch-icon.png')
def serve_touch_icon():
    """
    Serve the apple-touch-icon.png file from the static directory.
    
    :return: Apple touch icon file response
    """
    return send_from_directory(constants.STATIC_DIR, 'apple-touch-icon.png')

@static_bp.route('/robots.txt')
def serve_robots_txt():
    """
    Serve the robots.txt file from the static directory.
    
    :return: Apple touch icon file response
    """
    return send_from_directory(constants.STATIC_DIR, 'robots.txt')
