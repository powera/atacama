"""Auth tools. The require_auth web decorator."""

import os
from functools import wraps
from flask import render_template, session, g

from common.database import setup_database
from common.models import get_or_create_user

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                               client_id=os.getenv('GOOGLE_CLIENT_ID'))
                               
        # Store user info in g if not already there
        if not hasattr(g, 'user'):
            Session, db_success = setup_database()
            db_session = Session()
            try:
                g.user = get_or_create_user(db_session, session['user'])
            finally:
                db_session.close()
                
        return f(*args, **kwargs)
    return decorated_function
