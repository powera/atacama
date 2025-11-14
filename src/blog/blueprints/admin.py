"""Admin functionality for managing user access to restricted channels."""

import os
from typing import Dict, List

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

import constants
from common.base.logging_config import get_logger
from common.config.channel_config import AccessLevel, get_channel_manager
from models.database import db
from models.models import User, Email
from models.users import (
    is_user_admin, get_user_by_id,
    grant_channel_access_by_id, revoke_channel_access_by_id, get_user_channel_access_by_id,
    get_all_users
)
from models.messages import get_message_by_id
from atacama.decorators import require_auth, navigable

logger = get_logger(__name__)

# Get the blog module directory (parent of blueprints/)
blog_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

admin_bp = Blueprint('admin', __name__,
                    template_folder=os.path.join(blog_dir, 'templates'),
                    static_folder=os.path.join(blog_dir, 'static'))

def is_admin() -> bool:
    """Check if current user has admin access."""
    if not hasattr(g, 'user') or not g.user:
        return False
    return is_user_admin(g.user.email)

@admin_bp.route('/admin/users')
@require_auth
@navigable(name="List Users", category="admin")
def list_users():
    """Show list of users and their channel access."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('content.landing_page'))
        
    with db.session() as db_session:
        # Get all users using the function from models.users
        users = get_all_users(db_session)
        
        # Get channel access for each user
        user_access = []
        for user in users:
            access = get_user_channel_access_by_id(db_session, user.id)
            user_access.append({
                'user': user,
                'access': access
            })
            
        # Get admin-controlled channels from configuration
        channel_manager = get_channel_manager()
        admin_channels = [
            name for name in channel_manager.get_channel_names()
            if channel_manager.get_channel_config(name).requires_admin
        ]
            
        return render_template(
            'admin/users.html',
            users=user_access,
            channels=admin_channels
        )

@admin_bp.route('/admin/users/<int:user_id>/grant', methods=['POST'])
@require_auth
def grant_access(user_id: int):
    """Grant channel access to a user."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('content.landing_page'))
        
    channel = request.form.get('channel')
    if not channel:
        flash('Channel required')
        return redirect(url_for('admin.list_users'))
        
    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        flash('Invalid admin-controlled channel')
        return redirect(url_for('admin.list_users'))
        
    with db.session() as db_session:
        # Update admin channel access using convenience function
        success = grant_channel_access_by_id(db_session, user_id, channel)
        
        if success:
            db_session.commit()
            # Get user for display purposes only
            user = get_user_by_id(db_session, user_id)
            flash(f'Granted {channel} access to {user.email}')
        else:
            flash(f'Failed to grant {channel} access (user not found or invalid channel)')
        
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/admin/users/<int:user_id>/revoke', methods=['POST']) 
@require_auth
def revoke_access(user_id: int):
    """Revoke channel access from a user."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('content.landing_page'))
        
    channel = request.form.get('channel')
    if not channel:
        flash('Channel required')
        return redirect(url_for('admin.list_users'))
        
    channel = channel.lower()
    channel_config = get_channel_manager().get_channel_config(channel)
    if not channel_config or not channel_config.requires_admin:
        flash('Invalid admin-controlled channel')
        return redirect(url_for('admin.list_users'))
        
    with db.session() as db_session:
        # Update admin channel access using convenience function
        success = revoke_channel_access_by_id(db_session, user_id, channel)
        
        if success:
            db_session.commit()
            # Get user for display purposes only
            user = get_user_by_id(db_session, user_id)
            flash(f'Revoked {channel} access from {user.email}')
        else:
            flash(f'Failed to revoke {channel} access (user not found or invalid channel)')
        
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/admin/messages/<int:message_id>/rechannel', methods=['POST'])
@require_auth
def rechannel_message(message_id: int):
    """Change the channel of a message."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('content.landing_page'))
        
    new_channel = request.form.get('new_channel')
    if not new_channel:
        flash('New channel is required')
        return redirect(url_for('content.get_message', message_id=message_id))
        
    new_channel = new_channel.lower()
    channel_config = get_channel_manager().get_channel_config(new_channel)
    if not channel_config:
        flash('Invalid channel')
        return redirect(url_for('content.get_message', message_id=message_id))
        
    with db.session() as db_session:
        message = get_message_by_id(db_session, message_id)
        
        if not message:
            flash('Message not found')
            return redirect(url_for('content.landing_page'))
            
        old_channel = message.channel
        message.channel = new_channel
        
        db_session.commit()
        flash(f'Message re-channeled from {old_channel} to {new_channel}')
        
    return redirect(url_for('content.get_message', message_id=message_id))