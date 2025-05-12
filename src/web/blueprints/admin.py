"""Admin functionality for managing user access to restricted channels."""

import json
from datetime import datetime
from typing import Dict, List

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select

import constants
from common.auth import require_auth
from common.channel_config import AccessLevel, get_channel_manager
from common.database import db
from common.logging_config import get_logger
from common.models import User, Email
from common.navigation import navigable
from common.user_config import get_user_config_manager

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__)

def is_admin() -> bool:
    """Check if current user has admin access."""
    if not hasattr(g, 'user') or not g.user:
        return False
    user_config_manager = get_user_config_manager()
    return user_config_manager.is_admin(g.user.email)

@admin_bp.route('/admin/users')
@require_auth
@navigable(name="List Users", category="admin")
def list_users():
    """Show list of users and their channel access."""
    if not is_admin():
        flash('Admin access required')
        return redirect(url_for('content.landing_page'))
        
    with db.session() as db_session:
        # Use SQLAlchemy 2.0 style query
        stmt = select(User).order_by(User.email)
        users = db_session.execute(stmt).scalars().all()
        
        # Get channel access for each user
        user_access = []
        for user in users:
            access = json.loads(user.admin_channel_access or '{}')
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
        # Use SQLAlchemy 2.0 style query
        stmt = select(User).where(User.id == user_id)
        user = db_session.execute(stmt).scalar_one_or_none()
        
        if not user:
            flash('User not found')
            return redirect(url_for('admin.list_users'))
            
        # Update admin channel access
        access = json.loads(user.admin_channel_access or '{}')
        access[channel] = datetime.utcnow().isoformat()
        user.admin_channel_access = json.dumps(access)
        
        db_session.commit()
        flash(f'Granted {channel} access to {user.email}')
        
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
        # Use SQLAlchemy 2.0 style query
        stmt = select(User).where(User.id == user_id)
        user = db_session.execute(stmt).scalar_one_or_none()
        
        if not user:
            flash('User not found')
            return redirect(url_for('admin.list_users'))
            
        # Update admin channel access
        access = json.loads(user.admin_channel_access or '{}')
        access.pop(channel, None)
        user.admin_channel_access = json.dumps(access)
        
        db_session.commit()
        flash(f'Revoked {channel} access from {user.email}')
        
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
        # Use SQLAlchemy 2.0 style query
        stmt = select(Email).where(Email.id == message_id)
        message = db_session.execute(stmt).scalar_one_or_none()
        
        if not message:
            flash('Message not found')
            return redirect(url_for('content.landing_page'))
            
        old_channel = message.channel
        message.channel = new_channel
        
        db_session.commit()
        flash(f'Message re-channeled from {old_channel} to {new_channel}')
        
    return redirect(url_for('content.get_message', message_id=message_id))