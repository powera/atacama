"""Auth tools. The require_auth web decorator."""

import os
from functools import wraps
from flask import render_template, session, g

from common.database import db
from common.models import get_or_create_user

def _populate_user():
    """Helper to populate g.user from session if logged in."""
    if 'user' in session and not hasattr(g, 'user'):
        with db.session() as db_session:
            db_session.expire_on_commit = False
            g.user = get_or_create_user(db_session, session['user'])

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                               client_id=os.getenv('GOOGLE_CLIENT_ID'))
                               
        _populate_user()
        return f(*args, **kwargs)
    return decorated_function

def optional_auth(f):
    @wraps(f) 
    def decorated_function(*args, **kwargs):
        _populate_user()
        return f(*args, **kwargs)
    return decorated_function
