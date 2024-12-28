from flask import Blueprint, send_from_directory
import os

@app.route('/js/<path:filename>')
def serve_js(filename: str):
    """
    Serve JS files from the js directory.

    :param filename: Name of the JS file to serve
    :return: JS file response
    """
    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
    return send_from_directory(js_dir, filename)

@app.route('/css/<path:filename>')
def serve_css(filename: str):
    """
    Serve CSS files from the css directory.

    :param filename: Name of the CSS file to serve
    :return: CSS file response
    """
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    return send_from_directory(css_dir, filename)
