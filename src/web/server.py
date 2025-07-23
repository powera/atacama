#!/usr/bin/python3

""" Web server for atacama. """

import os
from pathlib import Path
from flask import Flask, request, g
from waitress import serve
from typing import Dict, Any, Optional, List, Tuple

import constants

from models.database import db
from common.config.channel_config import init_channel_manager, get_channel_manager
from common.config.domain_config import init_domain_manager, get_domain_manager
from common.services.archive import init_archive_service, get_archive_service
from common.base.logging_config import get_logger
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

def before_request_handler():
    """Handler to process domain and theme information before each request."""
    # Get host from request
    host = request.host
    
    # Get domain manager
    domain_manager = get_domain_manager()
    
    # Determine current domain based on host
    domain_key = domain_manager.get_domain_for_host(host)
    domain_config = domain_manager.get_domain_config(domain_key)
    
    # Get theme configuration
    theme_key = domain_config.theme
    theme_config = domain_manager.get_theme_config(theme_key)
    
    # Store in Flask's g object for access in views and templates
    g.current_domain = domain_key
    g.domain_config = domain_config
    g.theme_config = theme_config
    g.theme_css_files = theme_config.css_files
    g.theme_layout = theme_config.layout

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
    
    # Configure CORS for development mode
    if constants.is_development_mode():
        from flask_cors import CORS
        CORS(app, origins="*", supports_credentials=True)
        logger.info("CORS disabled for development mode - allowing all origins")
    
    # Initialize managers
    init_channel_manager()
    domain_manager = init_domain_manager()
    
    # Initialize archive service with configuration from domain manager
    archive_config = domain_manager.get_archive_config()
    if archive_config:
        init_archive_service(archive_config)
        logger.info("Archive service initialized")
    
    # Register before request handler for domain/theme processing
    app.before_request(before_request_handler)
    
    # Add template context processor for common functions
    @app.context_processor
    def inject_access_functions():
        from models.messages import get_user_allowed_channels, check_channel_access, check_message_access
        
        return {
            'get_user_allowed_channels': get_user_allowed_channels,
            'check_channel_access': check_channel_access,
            'check_message_access': check_message_access,
        }

    # Add template context processor for domain and theme info
    @app.context_processor
    def inject_domain_data():
        return {
            'current_domain': getattr(g, 'current_domain', 'default'),
            'domain_config': getattr(g, 'domain_config', None),
            'theme_config': getattr(g, 'theme_config', None),
            'theme_css_files': getattr(g, 'theme_css_files', []),
            'theme_layout': getattr(g, 'theme_layout', 'default'),
            'domain_manager': get_domain_manager(),
            'channel_manager': get_channel_manager()
        }

    # Add template context processor for development mode
    @app.context_processor
    def inject_development_mode():
        """Inject development mode flag based on FLASK_ENV environment variable."""
        is_development = constants.is_development_mode()
        flask_env = os.getenv('FLASK_ENV', 'production').lower()
        return {
            'is_development': is_development,
            'flask_env': flask_env
        }
    
    # Request logging (skip for testing)
    if not testing:
        from common.base.request_logger import RequestLogger
        request_logger = RequestLogger(app)

    # Register blueprints
    # Blog blueprints
    from web.blueprints.blog import BLOG_BLUEPRINTS
    for blueprint in BLOG_BLUEPRINTS:
        app.register_blueprint(blueprint)

    # Core blueprints
    from web.blueprints.core.static import static_bp
    app.register_blueprint(static_bp)

    from web.blueprints.core.auth import auth_bp
    app.register_blueprint(auth_bp)

    from web.blueprints.core.nav import nav_bp
    app.register_blueprint(nav_bp)

    from web.blueprints.core.debug import debug_bp
    app.register_blueprint(debug_bp)

    from web.blueprints.core.errors import errors_bp
    app.register_blueprint(errors_bp)

    # Other blueprints
    from web.blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)

    from web.blueprints.trakaido import trakaido_bp
    app.register_blueprint(trakaido_bp)

    return app

# The app instance will be created when needed
app = None

def get_app():
    """Get or create the Flask application instance."""
    global app
    if app is None:
        app = create_app()
    return app

def run_server(host: str = '0.0.0.0', port: int = 5000, debug: bool = False) -> None:
    """Run the server and start the email fetcher daemon."""
    # Database initialization will happen automatically when needed
    # since system is already initialized by create_app()
    logger.info(f"Starting message processor server on {host}:{port}")
    
    if debug:
        # Use Flask's built-in development server for debug mode
        app = get_app()
        app.config['DEBUG'] = True
        app.run(host=host, port=port, debug=True)
    else:
        # Use Waitress for production
        serve(get_app(), host=host, port=port)