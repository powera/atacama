"""Admin functionality for managing user access to restricted channels."""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import select
import json
from datetime import datetime
import enum
from typing import Dict, List

from common.auth import require_auth
from common.database import setup_database
from common.models import User, Channel
from common.logging_config import get_logger

logger = get_logger(__name__)
Session, db_success = setup_database()

admin_bp = Blueprint('admin', __name__)

class AdminRole(enum.Enum):
    """Define admin permission levels."""
    SUPER_ADMIN = "super_admin"    # Can manage other admins
    CHANNEL_ADMIN = "channel_admin" # Can grant channel access

# Store admin roles - in a real system, this would be in the database
ADMIN_USERS = {
    "powera@gmail.com": AdminRole.SUPER_ADMIN,
    "atacama@earlyversion.com": AdminRole.CHANNEL_ADMIN
}

def is_admin() -> bool:
    """Check if current user has admin access."""
    user = session.get('user')
    if not user or 'email' not in user:
        return False
    return user['email'] in ADMIN_USERS

@admin_bp.route('/admin/users')
@require_auth
def list_users():
    """Show list of users and their channel access."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('messages.landing_page'))
        
    db_session = Session()
    try:
        users = db_session.query(User).order_by(User.email).all()
        
        # Get channel access for each user
        user_access = []
        for user in users:
            access = json.loads(user.admin_channel_access or '{}')
            user_access.append({
                'user': user,
                'access': access
            })
            
        return render_template(
            'admin/users.html',
            users=user_access,
            channels=[c for c in Channel if c.value == 'orinoco']  # Only show admin-controlled channels
        )
    finally:
        db_session.close()

@admin_bp.route('/admin/users/<int:user_id>/grant', methods=['POST'])
@require_auth
def grant_access(user_id: int):
    """Grant channel access to a user."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('messages.landing_page'))
        
    channel = request.form.get('channel')
    if not channel:
        flash('Channel required')
        return redirect(url_for('admin.list_users'))
        
    try:
        channel_enum = Channel[channel.upper()]
    except KeyError:
        flash('Invalid channel')
        return redirect(url_for('admin.list_users'))
        
    db_session = Session()
    try:
        user = db_session.query(User).get(user_id)
        if not user:
            flash('User not found')
            return redirect(url_for('admin.list_users'))
            
        # Update admin channel access
        access = json.loads(user.admin_channel_access or '{}')
        access[channel_enum.value] = datetime.utcnow().isoformat()
        user.admin_channel_access = json.dumps(access)
        
        # Clear cached permissions
        from common.messages import check_admin_approval
        check_admin_approval.cache_clear()
        
        db_session.commit()
        flash(f'Granted {channel} access to {user.email}')
        
    except Exception as e:
        logger.error(f"Error granting access: {str(e)}")
        flash('Error granting access')
        
    finally:
        db_session.close()
        
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/admin/users/<int:user_id>/revoke', methods=['POST']) 
@require_auth
def revoke_access(user_id: int):
    """Revoke channel access from a user."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('messages.landing_page'))
        
    channel = request.form.get('channel')
    if not channel:
        flash('Channel required')
        return redirect(url_for('admin.list_users'))
        
    try:
        channel_enum = Channel[channel.upper()]
    except KeyError:
        flash('Invalid channel')
        return redirect(url_for('admin.list_users'))
        
    db_session = Session()
    try:
        user = db_session.query(User).get(user_id)
        if not user:
            flash('User not found')
            return redirect(url_for('admin.list_users'))
            
        # Update admin channel access
        access = json.loads(user.admin_channel_access or '{}')
        access.pop(channel_enum.value, None)
        user.admin_channel_access = json.dumps(access)
        
        # Clear cached permissions
        from common.messages import check_admin_approval
        check_admin_approval.cache_clear()
        
        db_session.commit()
        flash(f'Revoked {channel} access from {user.email}')
        
    except Exception as e:
        logger.error(f"Error revoking access: {str(e)}")
        flash('Error revoking access')
        
    finally:
        db_session.close()
        
    return redirect(url_for('admin.list_users'))
