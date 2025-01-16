from flask import Blueprint, render_template, jsonify, request, session, render_template_string
from flask import make_response, Response, redirect, url_for, flash
from sqlalchemy import text, select
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from common.auth import require_auth, optional_auth
from common.database import db
from common.models import Email, Channel, get_or_create_user
from common.messages import get_message_by_id, get_message_chain, get_filtered_messages, check_message_access

from common.logging_config import get_logger
logger = get_logger(__name__)

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/channels', methods=['GET', 'POST'])
@require_auth
def channel_preferences():
    """Show and update channel preferences for the logged-in user."""
    with db.session() as db_session:
        # Get current user
        user = get_or_create_user(db_session, session['user'])
        
        if request.method == 'POST':
            # Get enabled channels from form
            new_prefs = {}
            for channel in Channel:
                if channel != Channel.SANDBOX:  # Skip sandbox channel
                    channel_name = channel.value
                    # Check if channel is enabled in form
                    enabled = request.form.get(f'channel_{channel_name}') == 'on'
                    
                    # Special handling for politics channel
                    if channel == Channel.POLITICS:
                        if not session['user']['email'].endswith('@earlyversion.com'):
                            enabled = False
                            
                    new_prefs[channel_name] = enabled
            
            # Update user preferences
            user.channel_preferences = json.dumps(new_prefs)
            db_session.commit()
            flash('Channel preferences updated successfully', 'success')
            return redirect(url_for('messages.channel_preferences'))
            
        # For GET request, show current preferences
        current_prefs = json.loads(user.channel_preferences or '{}')
        is_early_version = session['user']['email'].endswith('@earlyversion.com')
        
        return render_template(
            'channel_preferences.html',
            preferences=current_prefs,
            channels=[c for c in Channel if c != Channel.SANDBOX],
            is_early_version=is_early_version
        )


@messages_bp.route('/nav')
@require_auth
def navigation():
    """Show site navigation/sitemap page."""
    # Get list of available channels for the user
    user_prefs = json.loads(session['user'].get('channel_preferences', '{}'))
    is_early_version = session['user']['email'].endswith('@earlyversion.com')
    
    # Only show channels the user has access to
    available_channels = []
    for channel in Channel:
        if channel not in (Channel.SANDBOX, Channel.PRIVATE):
            if channel == Channel.POLITICS:
                if is_early_version and user_prefs.get('politics', False):
                    available_channels.append(channel)
            elif user_prefs.get(channel.value, True):
                available_channels.append(channel)
    
    return render_template(
        'nav.html',
        channels=available_channels
    )

@messages_bp.route('/messages/<int:message_id>', methods=['GET'])
@optional_auth
def get_message(message_id: int):
    """
    Retrieve and display a single message.
    
    Args:
        message_id: ID of the message to display
    """
    with db.session() as db_session:
        message = db_session.query(Email).get(message_id)
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
            
        # Check access permissions
        if not check_message_access(message):
            if request.headers.get('Accept', '').startswith('text/html'):
                return redirect(url_for('auth.login'))
            return jsonify({'error': 'Authentication required'}), 401
        
        # Return HTML if requested
        if request.headers.get('Accept', '').startswith('text/html'):
            template = 'message.html'
            channel = message.channel.value if message.channel else None
            return render_template(
                template,
                message=message,
                created_at=message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                raw_content=message.content,
                quotes=message.quotes,
                channel=channel,
            )
                
        # Otherwise return JSON
        return jsonify({
            'id': message.id,
            'subject': message.subject,
            'content': message.content,
            'processed_content': message.processed_content,
            'created_at': message.created_at.isoformat(),
            'parent_id': message.parent_id,
            'channel': message.channel.value,
            'llm_annotations': json.loads(message.llm_annotations or '{}'),
            'quotes': [{'text': q.text, 'type': q.quote_type} for q in message.quotes]
        })


@messages_bp.route('/messages/<int:message_id>/chain', methods=['GET'])
@optional_auth
def view_chain(message_id: int):
    """
    Display the full chain of messages related to a given message ID.
    Shows the parent chain and all child messages in chronological order.
    
    Args:
        message_id: ID of the message to show the chain for
    """
    chain = get_message_chain(message_id)
    
    if not chain:
        return render_template('chain.html', error="Message or chain not found")
    
    # Check access permissions for all messages in chain
    for message in chain:
        if not check_message_access(message):
            if request.headers.get('Accept', '').startswith('text/html'):
                return redirect(url_for('auth.login'))
            return jsonify({'error': 'Authentication required'}), 401
    
    # Format timestamps for display
    for message in chain:
        message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
    
    # Return HTML if requested
    if request.headers.get('Accept', '').startswith('text/html'):
        return render_template(
            'chain.html',
            messages=chain,
            target_id=message_id,
            channel=chain[0].channel.value if (chain[0].channel) else None
        )
    
    # Otherwise return JSON
    return jsonify({
        'chain': [{
            'id': msg.id,
            'subject': msg.subject,
            'content': msg.content,
            'processed_content': msg.processed_content,
            'created_at': msg.created_at.isoformat(),
            'parent_id': msg.parent_id,
            'channel': msg.channel.value,
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
def message_stream(older_than_id=None, user_id=None, channel=None):
    """
    Show a stream of messages with optional filtering.
    Supports pagination and filtering by user or channel.
    """
    # Check if trying to access restricted channel
    if channel in ['private', 'politics'] and 'user' not in session:
        return redirect(url_for('auth.login'))
        
    with db.session() as db_session:
        messages, has_more = get_filtered_messages(
            db_session,
            older_than_id=older_than_id,
            user_id=user_id,
            channel=channel
        )
        
        # Filter out messages user doesn't have access to
        messages = [msg for msg in messages if check_message_access(msg)]

        # Get list of available channels for navigation
        channels = []
        if 'user' in session:
            user_prefs = json.loads(session['user'].get('channel_preferences', '{}'))
            for c in Channel:
                if c != Channel.SANDBOX:
                    if user_prefs.get(c.value, True):
                        channels.append(c.value)
        else:
            # Show public channels for anonymous users
            channels = [c.value for c in Channel 
                        if c not in (Channel.PRIVATE, Channel.POLITICS, Channel.SANDBOX)]

        return render_template(
            'stream.html',
            messages=messages,
            has_more=has_more,
            older_than_id=messages[-1].id if messages and has_more else None,
            current_user_id=user_id,
            current_channel=channel,
            available_channels=channels
        )


@messages_bp.route('/sitemap.xml')
def sitemap() -> str:
    """Generate sitemap.xml containing all public URLs."""
    with db.session() as db_session:
        # Get all messages and quotes
        messages = db_session.query(Email).order_by(Email.created_at.desc()).all()
        
        # Build list of URLs with last modified dates
        urls = []
        base_url = request.url_root.rstrip('/')
        
        # Add static pages
        urls.append({
            'loc': f"{base_url}/",
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
        })
        
        # Add channel pages
        for channel in Channel:
            # Only include public channels in sitemap
            if channel not in [Channel.PRIVATE, Channel.SANDBOX, Channel.POLITICS]:
                urls.append({
                    'loc': f"{base_url}/stream/channel/{channel.value}",
                    'lastmod': datetime.utcnow().strftime('%Y-%m-%d')
                })
        
        # Add all public messages
        for message in messages:
            if message.channel not in [Channel.PRIVATE, Channel.SANDBOX, Channel.POLITICS]:
                urls.append({
                    'loc': f"{base_url}/messages/{message.id}",
                    'lastmod': message.created_at.strftime('%Y-%m-%d')
                })
            
        # Generate XML
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
    with db.session() as db_session:
        # Test database connection
        db_session.execute(text('SELECT 1'))
        db_status = "Connected"

        # Fetch recent messages with their relationships
        messages = db_session.query(Email).options(
            joinedload(Email.parent),
            joinedload(Email.children),
            joinedload(Email.quotes)
        ).order_by(Email.created_at.desc()).limit(50).all()

        # Filter messages based on access permissions
        messages = [msg for msg in messages if check_message_access(msg)]

        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')

        # Get available channels for navigation
        channels = [c.value for c in Channel]
        
        # Only show restricted channels if user is logged in
        if 'user' not in session:
            channels = [c for c in channels if c not in ['private', 'politics']]

    # Check if user is authenticated via Google auth
    user = session.get('user')

    return render_template(
        'landing.html',
        db_status=db_status,
        messages=messages,
        user=user,
        available_channels=channels
    )
