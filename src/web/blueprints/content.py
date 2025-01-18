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
    g
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
from common.channel_config import get_channel_manager, AccessLevel
from common.logging_config import get_logger

logger = get_logger(__name__)

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/channels', methods=['GET', 'POST'])
@require_auth
def channel_preferences():
    """
    Show and update channel preferences for the logged-in user.
    
    :return: Rendered template response
    """
    channel_manager = get_channel_manager()
    
    with db.session() as db_session:
        user = get_or_create_user(db_session, session['user'])
        current_prefs = json.loads(user.channel_preferences or '{}')
        
        if request.method == 'POST':
            new_prefs = {}
            for channel_name in channel_manager.get_channel_names():
                new_prefs[channel_name] = request.form.get(f'channel_{channel_name}') == 'on'
                
            user.channel_preferences = json.dumps(new_prefs)
            db_session.commit()
            flash('Channel preferences updated successfully', 'success')
            return redirect(url_for('messages.channel_preferences'))
            
        return render_template(
            'channel_preferences.html',
            preferences=current_prefs,
            channels=channel_manager.channels,
            user=user,
            user_email=user.email
        )


@messages_bp.route('/nav')
@require_auth
def navigation() -> str:
    """
    Show site navigation/sitemap page.
    
    :return: Rendered template response
    """
    channel_manager = get_channel_manager()
    user_email = session['user']['email']
    
    # Get list of accessible channels
    available_channels = []
    for channel in channel_manager.channels:
        config = channel_manager.get_channel_config(channel)
        if config and check_channel_access(channel, g.user):
            available_channels.append((channel, config))
    
    return render_template(
        'nav.html',
        channels=available_channels
    )

@messages_bp.route('/messages/<int:message_id>', methods=['GET'])
@optional_auth
def get_message(message_id: int) -> Response:
    """
    Retrieve and display a single message.
    
    :param message_id: ID of the message to display
    :return: Response containing message data or error
    """
    with db.session() as db_session:
        message = db_session.query(Email).get(message_id)
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
            
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
                channel_config=channel_config
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

@messages_bp.route('/messages/<int:message_id>/chain', methods=['GET'])
@optional_auth
def view_chain(message_id: int) -> Response:
    """
    Display the full chain of messages related to a given message ID.
    
    :param message_id: ID of the target message
    :return: Response containing chain data or error
    """
    chain = get_message_chain(message_id)
    
    if not chain:
        return render_template('chain.html', error="Message or chain not found")
    
    # (currently) unneeded; access checked in get_message_chain
    # Check access permissions for all messages in chain
    #for message in chain:
    #    if not check_message_access(message):
    #        if request.headers.get('Accept', '').startswith('text/html'):
    #            return redirect(url_for('auth.login'))
    #        return jsonify({'error': 'Authentication required'}), 401
    
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
            channel_config=channel_config
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

@messages_bp.route('/')
@messages_bp.route('/stream')
@messages_bp.route('/stream/older/<int:older_than_id>')
@messages_bp.route('/stream/user/<int:user_id>')
@messages_bp.route('/stream/user/<int:user_id>/older/<int:older_than_id>')
@messages_bp.route('/stream/channel/<path:channel>')
@messages_bp.route('/stream/channel/<path:channel>/older/<int:older_than_id>')
@optional_auth
def message_stream(older_than_id: Optional[int] = None, 
                  user_id: Optional[int] = None,
                  channel: Optional[str] = None) -> str:
    """
    Show a stream of messages with optional filtering.
    
    :param older_than_id: Optional ID to paginate from
    :param user_id: Optional user ID to filter by
    :param channel: Optional channel name to filter by
    :return: Rendered template response
    """
    channel_manager = get_channel_manager()
    
    # Check channel access before querying
    if channel:
        config = channel_manager.get_channel_config(channel)
        if config and config.requires_auth and 'user' not in session:
            return redirect(url_for('auth.login'))
    
    with db.session() as db_session:
        messages, has_more = get_filtered_messages(
            db_session,
            older_than_id=older_than_id,
            user_id=user_id,
            channel=channel
        )
        
        # Get available channels
        channels = get_user_allowed_channels(g.user, ignore_preferences=False)

        return render_template(
            'stream.html',
            messages=messages,
            has_more=has_more,
            older_than_id=messages[-1].id if messages and has_more else None,
            current_user_id=user_id,
            current_channel=channel,
            available_channels=channels,
            channel_configs=channel_manager.channels
        )

@messages_bp.route('/sitemap.xml')
def sitemap() -> Response:
    """
    Generate sitemap.xml containing all public URLs.
    
    :return: XML response containing sitemap
    """
    channel_manager = get_channel_manager()
    
    with db.session() as db_session:
        messages = db_session.query(Email).order_by(Email.created_at.desc()).all()
        urls = []
        base_url = request.url_root.rstrip('/')
        
        urls.append({
            'loc': f"{base_url}/",
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })
        
        # Add public channel pages
        for channel_name, config in channel_manager.channels.items():
            if config.access_level == AccessLevel.PUBLIC:
                urls.append({
                    'loc': f"{base_url}/stream/channel/{channel_name}",
                    'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
                })
        
        # Add public messages
        for message in messages:
            config = channel_manager.get_channel_config(message.channel)
            if config and config.access_level == AccessLevel.PUBLIC:
                urls.append({
                    'loc': f"{base_url}/messages/{message.id}",
                    'lastmod': message.created_at.strftime('%Y-%m-%d')
                })
        
        sitemap_xml = render_template_string('''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {%- for url in urls %}
    <url>
        <loc>{{ url.loc | e }}</loc>
        <lastmod>{{ url.lastmod }}</lastmod>
    </url>
    {%- endfor %}
</urlset>''', urls=urls)
        
        response = make_response(sitemap_xml)
        response.headers['Content-Type'] = 'application/xml'
        return response


@messages_bp.route('/details')
@optional_auth
def landing_page():
    """Serve the landing page with basic service information and message list."""
    channel_manager = get_channel_manager()

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
            for message in messages:
                message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

            # Get available channels for user
            channels = get_user_allowed_channels(g.user, ignore_preferences=False)

        except Exception as e:
            logger.error(f"Database error in landing page: {str(e)}")
            db_status = f"Error: {str(e)}"
            messages = []
            channels = []

        return render_template(
            'landing.html',
            db_status=db_status,
            messages=messages,
            user=session.get('user'),
            available_channels=channels,
            channel_configs=channel_manager.channels
        )
