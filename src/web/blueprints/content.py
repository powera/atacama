"""Blueprint for handling content pages and message display."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from flask import (
    Blueprint, 
    render_template, 
    jsonify, 
    request, 
    session,
    render_template_string,
    make_response,
    Response,
    redirect, 
    url_for, 
    flash,
    g,
    abort
)
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload

from common.auth import require_auth, optional_auth
from common.database import db
from common.models import Email, get_or_create_user
from common.messages import (
    get_message_by_id,
    get_message_chain,
    get_filtered_messages,
    check_message_access,
    check_channel_access,
    get_user_allowed_channels
)
from common.navigation import navigable
from common.channel_config import get_channel_manager, AccessLevel
from common.domain_config import get_domain_manager
from common.logging_config import get_logger

from web.blueprints.admin import is_admin

logger = get_logger(__name__)

content_bp = Blueprint('content', __name__)


@content_bp.route('/channels', methods=['GET', 'POST'])
@require_auth
@navigable(name="Channel Preferences",
           description="Change which channels are in the stream view",
           category="user")
def channel_preferences():
    """
    Show and update channel preferences for the logged-in user.
    
    :return: Rendered template response
    """
    channel_manager = get_channel_manager()
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    with db.session() as db_session:
        user = get_or_create_user(db_session, session['user'])
        current_prefs = json.loads(user.channel_preferences or '{}')
        
        # Filter channels based on domain restrictions
        filtered_channels = {}
        for channel_name, config in channel_manager.channels.items():
            if domain_manager.is_channel_allowed(current_domain, channel_name):
                filtered_channels[channel_name] = config
        
        if request.method == 'POST':
            new_prefs = {}
            # Keep existing preferences for channels not in this domain
            for channel_name in channel_manager.get_channel_names():
                if channel_name in filtered_channels:
                    new_prefs[channel_name] = request.form.get(f'channel_{channel_name}') == 'on'
                else:
                    # Preserve existing preference for channels not in this domain
                    new_prefs[channel_name] = current_prefs.get(channel_name, False)
                
            user.channel_preferences = json.dumps(new_prefs)
            db_session.commit()
            flash('Channel preferences updated successfully', 'success')
            return redirect(url_for('content.channel_preferences'))
            
        return render_template(
            'channel_preferences.html',
            preferences=current_prefs,
            channels=filtered_channels,
            user=user,
            user_email=user.email,
            domain_manager=domain_manager,
            current_domain=current_domain
        )


@content_bp.route('/messages/<int:message_id>', methods=['GET'])
@optional_auth
def get_message(message_id: int) -> Response:
    """
    Retrieve and display a single message.
    
    :param message_id: ID of the message to display
    :return: Response containing message data or error
    """
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    with db.session() as db_session:
        message = db_session.query(Email).get(message_id)
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
            
        # Check channel access for domain
        if not domain_manager.is_channel_allowed(current_domain, message.channel):
            if request.headers.get('Accept', '').startswith('text/html'):
                abort(404, f"Message not available on this domain")
            return jsonify({'error': 'Message not available on this domain'}), 404
            
        if not check_message_access(message):
            if request.headers.get('Accept', '').startswith('text/html'):
                return redirect(url_for('auth.login'))
            return jsonify({'error': 'Authentication required'}), 401
        
        if request.headers.get('Accept', '').startswith('text/html'):
            channel_manager = get_channel_manager()
            channel_config = channel_manager.get_channel_config(message.channel)
            
            return render_template(
                'message.html',
                message=message,
                created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                raw_content=message.content,
                quotes=message.quotes,
                channel=message.channel,
                channel_manager=channel_manager,
                channel_config=channel_config,
                domain_manager=domain_manager,
                current_domain=current_domain
            )
                
        return jsonify({
            'id': message.id,
            'subject': message.subject,
            'content': message.content,
            'processed_content': message.processed_content,
            'created_at': message.created_at.isoformat(),
            'parent_id': message.parent_id,
            'channel': message.channel,
            'llm_annotations': json.loads(message.llm_annotations or '{}'),
            'quotes': [{'text': q.text, 'type': q.quote_type} for q in message.quotes]
        })

@content_bp.route('/messages/<int:message_id>/chain', methods=['GET'])
@optional_auth
def view_chain(message_id: int) -> Response:
    """
    Display the full chain of messages related to a given message ID.
    
    :param message_id: ID of the target message
    :return: Response containing chain data or error
    """
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    chain = get_message_chain(message_id)
    
    if not chain:
        return render_template('chain.html', error="Message or chain not found")
    
    # Check domain access for the chain (based on first message's channel)
    if chain and not domain_manager.is_channel_allowed(current_domain, chain[0].channel):
        if request.headers.get('Accept', '').startswith('text/html'):
            abort(404, f"Message chain not available on this domain")
        return jsonify({'error': 'Message chain not available on this domain'}), 404
    
    # Format timestamps and get channel configuration
    channel_manager = get_channel_manager()
    channel_config = None
    if chain:
        channel_config = channel_manager.get_channel_config(chain[0].channel)
        for message in chain:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
    
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'chain.html',
            messages=chain,
            target_id=message_id,
            channel=chain[0].channel if chain else None,
            channel_manager=channel_manager,
            channel_config=channel_config,
            domain_manager=domain_manager,
            current_domain=current_domain
        )
    
    return jsonify({
        'chain': [{
            'id': msg.id,
            'subject': msg.subject,
            'content': msg.content,
            'processed_content': msg.processed_content,
            'created_at': msg.created_at.isoformat(),
            'parent_id': msg.parent_id,
            'channel': msg.channel,
            'is_target': msg.id == message_id
        } for msg in chain]
    })

@content_bp.route('/')
@content_bp.route('/stream')
@content_bp.route('/stream/older/<int:older_than_id>')
@content_bp.route('/stream/before/<string:tsdate>/')
@content_bp.route('/stream/before/<string:tsdate>/<string:tstime>/')
@content_bp.route('/stream/channel/<string:channel>')
@content_bp.route('/stream/channel/<string:channel>/older/<int:older_than_id>')
@content_bp.route('/stream/channel/<string:channel>/before/<string:tsdate>/')
@content_bp.route('/stream/channel/<string:channel>/before/<string:tsdate>/<string:tstime>/')
@optional_auth
def message_stream(older_than_id: Optional[int] = None,
                  channel: Optional[str] = None,
                  tsdate: Optional[str] = None, tstime: Optional[str] = None) -> str:
    """
    Show a stream of messages with optional filtering.
    
    :param older_than_id: Optional ID to paginate from
    :param channel: Optional channel name to filter by
    :return: Rendered template response
    """

    older_than_timestamp = None
    
    # Handle timestamp-based filtering
    if tsdate:
        if not tstime:
            # If time is not provided, default to end of day
            tstime = '235959'
        try:
            # Parse timestamp from URL format YYYY-MM-DD and HHMMSS
            timestamp_str = f"{tsdate} {tstime[:2]}:{tstime[2:4]}:{tstime[4:6]}"
            older_than_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, IndexError):
            # If timestamp is invalid, ignore it
            pass

    channel_manager = get_channel_manager()
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    # Check channel access before querying
    if channel:
        # First check if channel is allowed on this domain
        if not domain_manager.is_channel_allowed(current_domain, channel):
            abort(404, f"Channel not available on this domain")
            
        config = channel_manager.get_channel_config(channel)
        if config and config.requires_auth and 'user' not in session:
            return redirect(url_for('auth.login'))
    
    with db.session() as db_session:
        messages, has_more = get_filtered_messages(
            db_session,
            older_than_id=older_than_id,
            older_than_timestamp=older_than_timestamp,
            channel=channel,
            limit=10
        )
        
        # Get available channels
        channels = get_user_allowed_channels(g.user, ignore_preferences=False)
        
        # Filter channels based on domain restrictions
        domain_allowed_channels = []
        for ch in channels:
            if domain_manager.is_channel_allowed(current_domain, ch):
                domain_allowed_channels.append(ch)
        
        # If viewing all channels, filter messages by domain-allowed channels
        if not channel and not domain_manager.get_domain_config(current_domain).allows_all_channels:
            messages = [msg for msg in messages if domain_manager.is_channel_allowed(current_domain, msg.channel)]

        # Determine pagination style for next page
        # If current page uses ID-based pagination, continue with that
        use_id_pagination = older_than_id is not None
        
        # For pagination, get the appropriate value from the oldest message
        older_than_next_id = None
        older_than_next_tsdate = None
        older_than_next_tstime = None
        
        if messages and has_more:
            if use_id_pagination:
                older_than_next_id = messages[-1].id
            else:
                # Format timestamp as YYYYMMDD-HHMMSS for URL
                dt = messages[-1].created_at
                older_than_next_tsdate = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
                older_than_next_tstime = f"{dt.hour:02d}{dt.minute:02d}{dt.second:02d}"

        return render_template(
            'stream.html',
            messages=messages,
            has_more=has_more,
            older_than_id=older_than_next_id,
            older_than_tsdate=older_than_next_tsdate,
            older_than_tstime=older_than_next_tstime,
            use_id_pagination=use_id_pagination,
            current_channel=channel,
            available_channels=domain_allowed_channels,
            channel_manager=channel_manager,
            domain_manager=domain_manager,
            current_domain=current_domain
        )


@content_bp.route('/details')
@optional_auth
@navigable(name="Message List", category="admin")
def landing_page():
    """Serve the landing page with basic service information and message list."""
    channel_manager = get_channel_manager()
    domain_manager = get_domain_manager()
    current_domain = g.current_domain

    with db.session() as db_session:
        try:
            db_session.execute(text('SELECT 1'))
            db_status = "Connected"

            messages = db_session.query(Email).options(
                joinedload(Email.parent),
                joinedload(Email.children),
                joinedload(Email.quotes)
            ).order_by(Email.created_at.desc()).limit(50).all()

            # Get user if logged in
            user = None
            if 'user' in session:
                user = get_or_create_user(db_session, session['user'])

            # Filter messages and get available channels
            messages = [msg for msg in messages if check_message_access(msg)]
            
            # Further filter messages based on domain restrictions
            if not domain_manager.get_domain_config(current_domain).allows_all_channels:
                domain_channels = domain_manager.get_allowed_channels(current_domain)
                messages = [msg for msg in messages if msg.channel in domain_channels]
                
            for message in messages:
                message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

            # Get available channels for user
            user_channels = get_user_allowed_channels(g.user, ignore_preferences=False)
            
            # Filter channels based on domain restrictions
            if not domain_manager.get_domain_config(current_domain).allows_all_channels:
                domain_channels = domain_manager.get_allowed_channels(current_domain)
                available_channels = [c for c in user_channels if c in domain_channels]
            else:
                available_channels = user_channels

        except Exception as e:
            logger.error(f"Database error in landing page: {str(e)}")
            db_status = f"Error: {str(e)}"
            messages = []
            available_channels = []

        return render_template(
            'landing.html',
            db_status=db_status,
            messages=messages,
            user=session.get('user'),
            is_admin=is_admin(),
            available_channels=available_channels,
            channel_configs=channel_manager.channels,
            domain_manager=domain_manager,
            current_domain=current_domain
        )