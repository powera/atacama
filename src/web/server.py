#!/usr/bin/python3

""" Web server for atacama. """

import os
from pathlib import Path

from flask import Flask
from waitress import serve
from typing import Dict, Any, Optional, List, Tuple

import constants

from common.database import setup_database
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

app = Flask(__name__)
app.secret_key = load_or_create_secret_key()

from common.request_logger import RequestLogger
request_logger = RequestLogger(app)

# Serve Quotes HTML pages
from web.blueprints.quotes import quotes_bp
app.register_blueprint(quotes_bp)

# Serve CSS, JS, etc.
from web.blueprints.static import static_bp
app.register_blueprint(static_bp)

# Login, logout, Google Auth callbacks
from web.blueprints.auth import auth_bp
app.register_blueprint(auth_bp)

# Message display handlers
from web.blueprints.content import messages_bp
app.register_blueprint(messages_bp)

# Submit message form
from web.blueprints.submit import submit_bp
app.register_blueprint(submit_bp)

# Admin handlers
from web.blueprints.admin import admin_bp
app.register_blueprint(admin_bp)

# Debug handlers
from web.blueprints.debug import debug_bp
app.register_blueprint(debug_bp)

# Error handlers
from web.blueprints.errors import errors_bp
app.register_blueprint(errors_bp)

def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """Run the server and start the email fetcher daemon."""
    Session, db_success = setup_database()

    if not db_success:
        logger.error("Database initialization failed, cannot start web server")
        return
        
    logger.info(f"Starting message processor server on {host}:{port}")
    serve(app, host=host, port=port)
