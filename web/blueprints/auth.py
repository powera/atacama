from flask import Blueprint, request, render_template, session, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return render_template('login.html', 
                                   client_id=os.getenv('GOOGLE_CLIENT_ID'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login')
def login():
    return render_template('login.html', 
                         client_id=os.getenv('GOOGLE_CLIENT_ID'))

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Google ID token and extract user info.
    
    :param token: Google ID token
    :return: User info dict if valid, None if invalid
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            os.getenv('GOOGLE_CLIENT_ID')
        )
        
        # Verify claims
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            logger.error("Invalid token issuer")
            return None
            
        if idinfo['exp'] < datetime.now().timestamp():
            logger.error("Token expired")
            return None
            
        if idinfo['aud'] != os.getenv('GOOGLE_CLIENT_ID'):
            logger.error("Invalid audience")
            return None
            
        return {
            'email': idinfo['email'],
            'name': idinfo.get('name', ''),
            'picture': idinfo.get('picture', ''),
            'exp': idinfo['exp']
        }
        
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        return None

@auth_bp.route('/oauth2callback')
def callback():
    """Handle OAuth 2.0 callback from Google."""
    # Check for OAuth errors
    if 'error' in request.args:
        logger.error(f"OAuth error: {request.args.get('error')}")
        return redirect(url_for('login'))
    
    # Get ID token from request
    token = request.args.get('credential')
    if not token:
        logger.error("No credential in callback")
        return redirect(url_for('login'))
        
    # Verify token and get user info
    user_info = verify_token(token)
    if not user_info:
        return redirect(url_for('login'))
        
    # Store user info in session
    session['user'] = user_info
    session.permanent = True
    
    return redirect(url_for('landing_page'))

@auth_bp.route('/logout')
def logout():
    """Clear user session."""
    session.clear()
    return redirect(url_for('login'))
