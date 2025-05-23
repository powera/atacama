"""Auth tools. The require_auth web decorator."""

import os
from functools import wraps
from flask import render_template, session, g

from models.database import db
from models import get_or_create_user
from common.config.user_config import get_user_config_manager

def _populate_user():
    """Helper to populate g.user from session if logged in."""
    if hasattr(g, 'user'):  # redundant
        return
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
    
    If a user is not logged in (i.e., 'user' is not in the session), this
    redirects to the login page. Otherwise, populate g.user and call the
    decorated function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                               client_id=os.getenv('GOOGLE_CLIENT_ID'))
                               
        _populate_user()
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