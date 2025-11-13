"""Auth tools. The require_auth web decorator."""

import os
import logging
from functools import wraps
from datetime import datetime, timedelta
from flask import render_template, session, g, request, jsonify

from models.database import db
from models import get_or_create_user
from models.models import User, UserToken
from common.config.user_config import get_user_config_manager

logger = logging.getLogger(__name__)

# Token expiration period (120 days)
TOKEN_EXPIRATION_DAYS = 120

def _populate_user():
    """Helper to populate g.user from session or auth token if logged in."""
    if hasattr(g, 'user'):  # already populated
        return
    
    # First, try to authenticate via auth token (for mobile/API requests)
    auth_token = request.headers.get('Authorization')
    if auth_token:
        # Support both "Bearer <token>" and just "<token>" formats
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]

        with db.session() as db_session:
            db_session.expire_on_commit = False
            # Query the new UserToken table
            token_obj = db_session.query(UserToken).filter_by(token=auth_token).first()
            if token_obj:
                # Check if token has expired
                token_age = datetime.utcnow() - token_obj.created_at
                if token_age > timedelta(days=TOKEN_EXPIRATION_DAYS):
                    # Token expired, delete it
                    logger.warning(f"Auth token expired for user {token_obj.user.email}. Token age: {token_age.days} days")
                    db_session.delete(token_obj)
                    db_session.commit()
                    g.user = None
                    return

                g.user = token_obj.user
                return
            else:
                logger.warning(f"Auth token provided but not found in database: {auth_token[:8]}... (truncated)")
                g.user = None
                return
    
    # Fall back to session-based authentication
    if 'user' in session:
        with db.session() as db_session:
            db_session.expire_on_commit = False
            g.user = get_or_create_user(db_session, session['user'])
    else:  # user not in session
        g.user = None

def optional_auth(f):
    """Decorator that optionally populates g.user if a user is logged in, allowing access to both authenticated and unauthenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        _populate_user()
        return f(*args, **kwargs)
    return decorated_function

def require_auth(f):
    """
    Decorator to require authentication before accessing a route.
    
    Supports both session-based and token-based authentication.
    For API requests (with Authorization header or JSON content type),
    returns JSON error. Otherwise redirects to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        _populate_user()
        
        if not g.user:
            # Check if this is an API request
            is_api_request = (
                request.headers.get('Authorization') or
                request.path.startswith('/api/') or
                request.headers.get('Content-Type', '').startswith('application/json')
            )
            
            if is_api_request:
                return jsonify({
                    'error': 'Authentication required',
                    'code': 'UNAUTHORIZED'
                }), 401
            else:
                return render_template('login.html', 
                                   client_id=os.getenv('GOOGLE_CLIENT_ID'))
        
        return f(*args, **kwargs)

    decorated_function.__auth_required__ = True
    return decorated_function

def require_admin(f):
    """
    Decorator that requires admin access before accessing a route.
    
    If a user is not logged in (i.e., 'user' is not in the session), this
    redirects to the login page. Otherwise, populate g.user and check if
    the user has admin access. If not, return a 403 error.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                                   client_id=os.getenv('GOOGLE_CLIENT_ID'))
                               
        _populate_user()
        
        # Check if user has admin access
        user_config_manager = get_user_config_manager()
        if not user_config_manager.is_admin(g.user.email):
            return render_template('error.html', 
                                error='Admin access required',
                                title='Forbidden'), 403
        
        return f(*args, **kwargs)

    decorated_function.__auth_required__ = True
    decorated_function.__admin_required__ = True
    return decorated_function