"""Authentication blueprint handling Google OAuth login flow."""

import os
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from flask import Blueprint, request, render_template, session, redirect, url_for, g, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests

from web.decorators import require_auth
from models.database import db
from models import get_or_create_user
from models.models import User
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager

logger = get_logger(__name__)

auth_bp = Blueprint('auth', __name__)

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

@auth_bp.route('/login')
def login():
    """Render login page with Google sign-in."""
    # Store the requested URL for post-login redirect
    session['post_login_redirect'] = request.args.get('next', '/')
    
    # Check if this is a popup login request
    popup_mode = request.args.get('popup', '').lower() == 'true'
    session['popup_mode'] = popup_mode
    
    # Check if this is a mobile OAuth request
    mobile_mode = request.args.get('mobile', '').lower() == '1'
    redirect_uri = request.args.get('redirect', '')
    
    if mobile_mode and redirect_uri:
        session['mobile_mode'] = True
        session['mobile_redirect'] = redirect_uri
        logger.info(f"Mobile OAuth flow initiated with redirect: {redirect_uri}")
    
    template = 'login_popup.html' if popup_mode else 'login.html'
    
    return render_template(
        template,
        client_id=GOOGLE_CLIENT_ID,
        popup_mode=popup_mode
    )

@auth_bp.route('/logout')
def logout():
    """Clear user session and redirect to login."""
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/logout', methods=['POST'])
@require_auth
def api_logout():
    """
    Revoke the current auth token for mobile/API clients.
    
    Requires Authorization header with valid token.
    Returns JSON response indicating success or failure.
    """
    try:
        with db.session() as db_session:
            # g.user is already populated by @require_auth
            if g.user and g.user.auth_token:
                # Re-query the user to get a session-bound instance
                user = db_session.query(User).filter_by(id=g.user.id).first()
                if user:
                    user.auth_token = None
                    user.auth_token_created_at = None
                    db_session.commit()
                    logger.info(f"Revoked auth token for user {user.email}")
                    return jsonify({'success': True, 'message': 'Token revoked'}), 200
            
            return jsonify({'success': False, 'error': 'No token to revoke'}), 400
            
    except Exception as e:
        logger.error(f"Error revoking token: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

def generate_auth_token() -> str:
    """
    Generate a secure random auth token for mobile/API authentication.
    
    :return: A secure random token string
    """
    return secrets.token_urlsafe(32)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Google ID token and extract user info.
    
    :param token: Google ID token to verify
    :return: User info dict if valid, None if invalid
    :raises: Various exceptions if token verification fails
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        # Verify essential claims
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            logger.error("Invalid token issuer")
            return None
            
        if idinfo['exp'] < datetime.now().timestamp():
            logger.error("Token expired")
            return None
            
        if idinfo['aud'] != GOOGLE_CLIENT_ID:
            logger.error("Invalid audience")
            return None
            
        # Extract relevant user info
        return {
            'email': idinfo['email'],
            'name': idinfo.get('name', ''),  # Fallback to empty string
            'picture': idinfo.get('picture', ''),
            'exp': idinfo['exp']
        }
        
    except ValueError as e:
        logger.error(f"Invalid token format: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        return None

@auth_bp.route('/oauth2callback')
def callback():
    """
    Handle OAuth 2.0 callback from Google.
    
    Verifies the ID token, creates/updates user record, and establishes session.
    """
    # Check for OAuth errors
    if 'error' in request.args:
        logger.error(f"OAuth error: {request.args.get('error')}")
        return redirect(url_for('auth.login'))
    
    # Get ID token from request
    token = request.args.get('credential')
    if not token:
        logger.error("No credential in callback")
        return redirect(url_for('auth.login'))
        
    # Verify token and get user info
    user_info = verify_token(token)
    if not user_info:
        return redirect(url_for('auth.login'))
        
    try:
        # Create or update user record
        with db.session() as db_session:
            db_session.expire_on_commit = False
            db_user = get_or_create_user(db_session, user_info)
            
            # Store minimal user info in session
            session['user'] = {
                'email': user_info['email'],
                'name': user_info['name'],
                'id': db_user.id
            }
            session.permanent = True
            
            # Initialize user's channel preferences if needed
            if not db_user.channel_preferences:
                channel_manager = get_channel_manager()
                db_user.channel_preferences = {
                    channel: channel in channel_manager.default_preferences
                    for channel in channel_manager.get_channel_names()
                }
            
            # Check if this is a mobile OAuth flow
            mobile_mode = session.pop('mobile_mode', False)
            mobile_redirect = session.pop('mobile_redirect', None)
            
            if mobile_mode and mobile_redirect:
                # Generate and store auth token for mobile app
                auth_token = generate_auth_token()
                db_user.auth_token = auth_token
                db_user.auth_token_created_at = datetime.utcnow()
                db_session.commit()
                
                logger.info(f"Generated auth token for user {db_user.email} (mobile OAuth)")
                
                # Redirect to the mobile app's custom URL scheme with the token
                redirect_url = f"{mobile_redirect}?token={auth_token}"
                return redirect(redirect_url)
    
    except Exception as e:
        logger.error(f"Database error in callback: {str(e)}")
        return redirect(url_for('auth.login'))
    
    # Check if this was a popup login
    popup_mode = session.pop('popup_mode', False)
    
    if popup_mode:
        # For popup mode, redirect to success page that will close the popup
        return render_template(
            'login_success_popup.html',
            user=session['user']
        )
    else:
        # Normal redirect behavior
        return redirect(session.pop('post_login_redirect', '/'))
