#!/usr/bin/python3

""" Web server for atacama. """

import os
from pathlib import Path

from flask import Flask
from waitress import serve
from typing import Dict, Any, Optional, List, Tuple

import constants

from common.database import db
from common.logging_config import get_logger
logger = get_logger(__name__)

def load_or_create_secret_key() -> str:
    """
    Load Flask secret key from file or create new one if none exists.
    
    :return: Secret key string
    :raises: RuntimeError if key directory is not writable
    """
    # First check environment variable
    if env_key := os.getenv('FLASK_SECRET_KEY'):
        return env_key
        
    key_path = Path(constants.KEY_DIR) / 'flask_secret_key'
    
    try:
        # Ensure key directory exists
        key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Try to load existing key
        if key_path.exists():
            return key_path.read_text().strip()
            
        # Generate new key if none exists
        import secrets
        new_key = secrets.token_hex(32)
        key_path.write_text(new_key)
        return new_key
        
    except (OSError, IOError) as e:
        logger.error(f"Failed to access secret key file: {e}")
        raise RuntimeError(f"Could not access secret key directory: {e}")

def create_app(testing: bool = False) -> Flask:
    """
    Create and configure Flask application instance.
    
    :param testing: Whether to configure app for testing
    :return: Configured Flask app
    """
    # Initialize system state before creating app
    if testing:
        constants.init_testing()

    # For production, initialization should already be done by launch.py
    if not constants.INITIALIZED:
        raise RuntimeError("System not initialized. In production, launch.py must initialize the system.")

    app = Flask(__name__)
    
    if not testing:
        app.secret_key = load_or_create_secret_key()
    else:
        app.secret_key = 'test-key'
    
    # Request logging (skip for testing)
    if not testing:
        from common.request_logger import RequestLogger
        request_logger = RequestLogger(app)

    # Register blueprints
    from web.blueprints.quotes import quotes_bp
    app.register_blueprint(quotes_bp)

    from web.blueprints.static import static_bp
    app.register_blueprint(static_bp)

    from web.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    from web.blueprints.content import content_bp
    app.register_blueprint(content_bp)

    from web.blueprints.article import articles_bp
    app.register_blueprint(articles_bp)

    from web.blueprints.submit import submit_bp
    app.register_blueprint(submit_bp)

    from web.blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)

    from web.blueprints.debug import debug_bp
    app.register_blueprint(debug_bp)

    from web.blueprints.errors import errors_bp
    app.register_blueprint(errors_bp)

    return app

# The app instance will be created when needed
app = None

def get_app():
    """Get or create the Flask application instance."""
    global app
    if app is None:
        app = create_app()
    return app

def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """Run the server and start the email fetcher daemon."""
    # Database initialization will happen automatically when needed
    # since system is already initialized by create_app()
    logger.info(f"Starting message processor server on {host}:{port}")
    serve(get_app(), host=host, port=port)
