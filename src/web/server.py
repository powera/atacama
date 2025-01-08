#!/usr/bin/python3

""" Web server for atacama. """

from flask import Flask
from waitress import serve
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from common.logging_config import get_logger
logger = get_logger(__name__)

from common.database import setup_database
Session, db_success = setup_database()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')  # Change in production

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
from web.blueprints.messages import messages_bp
app.register_blueprint(messages_bp)

# Submit message form
from web.blueprints.submit import submit_bp
app.register_blueprint(submit_bp)

# Debug handlers
from web.blueprints.debug import debug_bp
app.register_blueprint(debug_bp)

# Error handlers
from web.blueprints.errors import errors_bp
app.register_blueprint(errors_bp)

def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """Run the server and start the email fetcher daemon."""
    if not db_success:
        logger.error("Database initialization failed, cannot start web server")
        return
        
    logger.info(f"Starting message processor server on {host}:{port}")
    serve(app, host=host, port=port)
