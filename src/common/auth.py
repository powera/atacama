"""Auth tools.  The require_auth web decorator."""

import os
from functools import wraps

from flask import render_template, session

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                                   client_id=os.getenv('GOOGLE_CLIENT_ID'))
        return f(*args, **kwargs)
    return decorated_function

