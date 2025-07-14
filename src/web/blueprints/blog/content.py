"""Blueprint for handling content pages and message display."""

# Standard library imports
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
from flask import (
    Blueprint,
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload, selectinload

# Local application imports
from common.base.logging_config import get_logger
from common.config.channel_config import AccessLevel, get_channel_manager
from common.config.domain_config import get_domain_manager
from models import get_or_create_user
from models.database import db
from models.messages import (
    check_channel_access,
    check_message_access,
    get_domain_filtered_messages,
    get_filtered_messages,
    get_message_by_id,
    get_message_chain,
    get_user_allowed_channels
)

from models.models import Message, Article, ReactWidget, Quote, Email
from models.users import is_user_admin
from web.blueprints.core.errors import handle_error
from web.decorators import navigable, navigable_per_channel, optional_auth, require_auth

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
            user_email=user.email
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
            return handle_error(
                "404",
                "Message Not Found",
                "The requested message could not be found.",
                f"Message ID: {message_id}"
            )
            
        # Check channel access for domain
        if not domain_manager.is_channel_allowed(current_domain, message.channel):
            return handle_error(
                "404",
                "Message Not Available",
                "This message is not available on this domain.",
                f"Message channel {message.channel} not allowed on domain {current_domain}"
            )
            
        if not check_message_access(message):
            if request.headers.get('Accept', '').startswith('text/html'):
                return redirect(url_for('auth.login'))
            return handle_error(
                "401",
                "Authentication Required",
                "You need to be logged in to view this message.",
                "Message requires authentication"
            )
        
        if request.headers.get('Accept', '').startswith('text/html'):
            channel_config = get_channel_manager().get_channel_config(message.channel)
            
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
        return handle_error(
            "404",
            "Chain Not Found", 
            "The message chain could not be found. The message may not exist or may not have a chain.",
            f"Message ID: {message_id}"
        )
    
    # Check domain access for the chain (based on first message's channel)
    if chain and not domain_manager.is_channel_allowed(current_domain, chain[0].channel):
        return handle_error(
            "404",
            "Chain Not Available",
            "This message chain is not available on this domain.",
            f"Message channel {chain[0].channel} not allowed on domain {current_domain}"
        )
    
    # Format timestamps and get channel configuration
    channel_config = None
    if chain:
        channel_config = get_channel_manager().get_channel_config(chain[0].channel)
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
@navigable_per_channel(name="Message Stream",
                      description="Stream for this channel",
                      order=100)
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

    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    # Check channel access before querying
    if channel:
        # First check if channel is allowed on this domain
        if not domain_manager.is_channel_allowed(current_domain, channel):
            return handle_error(
                "404",
                "Channel Not Available",
                "This channel is not available on this domain.",
                f"Channel {channel} not allowed on domain {current_domain}"
            )
            
        config = get_channel_manager().get_channel_config(channel)
        if config and config.requires_auth and 'user' not in session:
            return redirect(url_for('auth.login'))
    
    with db.session() as db_session:
        messages, has_more = get_domain_filtered_messages(
            db_session,
            older_than_id=older_than_id,
            older_than_timestamp=older_than_timestamp,
            channel=channel,
            domain=current_domain,
            limit=10
        )
        
        # Get available channels
        channels = get_user_allowed_channels(g.user, ignore_preferences=False)
        
        # Filter channels based on domain restrictions
        domain_allowed_channels = []
        for ch in channels:
            if domain_manager.is_channel_allowed(current_domain, ch):
                domain_allowed_channels.append(ch)

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
            available_channels=domain_allowed_channels
        )


@content_bp.route('/details')
@optional_auth
@navigable(name="Detailed Message List", category="admin")
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
            is_admin=is_user_admin(g.user.email if g.user else None),
            available_channels=available_channels,
            channel_configs=channel_manager.channels
        )
    

@content_bp.route('/all')
@content_bp.route('/all/before/<string:tsdate>/')
@content_bp.route('/all/before/<string:tsdate>/<string:tstime>/')
@optional_auth
@navigable(name="All Messages", 
          description="View all types of messages (emails, articles, widgets, quotes)",
          category="main")
def all_messages(tsdate: Optional[str] = None, tstime: Optional[str] = None):
    """
    Display a unified stream of all message types with metadata and links.
    Uses datetime-based pagination like the stream view.
    """
    
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    # Handle timestamp-based filtering
    older_than_timestamp = None
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
    
    with db.session() as db_session:
        # Get user-allowed channels
        allowed_channels = get_user_allowed_channels(g.user, ignore_preferences=True)
        
        # Filter channels based on domain restrictions
        if not domain_manager.get_domain_config(current_domain).allows_all_channels:
            domain_channels = domain_manager.get_allowed_channels(current_domain)
            allowed_channels = [c for c in allowed_channels if c in domain_channels]
        
        # Query Messages table with proper filtering
        query = db_session.query(Message).options(
            selectinload(Message.author)
        ).filter(
            Message.channel.in_(allowed_channels)
        )
        
        # Apply timestamp filter if provided
        if older_than_timestamp:
            query = query.filter(Message.created_at < older_than_timestamp)
        
        # Get messages ordered by creation date (newest first)
        limit = 10
        messages = query.order_by(Message.created_at.desc()).limit(limit + 1).all()
        
        # Check if there are more messages
        has_more = len(messages) > limit
        messages = messages[:limit]
        
        # Transform messages into display format
        display_messages = []
        
        for message in messages:
            # Get type-specific data by querying the specific table
            type_specific_data = None
            message_url = None
            preview = None
            title = None
            display_date = message.created_at
            
            if message.message_type.value == 'email':
                email = db_session.query(Email).get(message.id)
                if email:
                    type_specific_data = email
                    title = email.subject or '(No Subject)'
                    # Use plain content for preview to avoid HTML tag truncation issues; "preview_content" is HTML rendered and should not be truncated further.
                    preview_text = email.content or ''
                    if len(preview_text) > 200:
                        preview = preview_text[:200] + '...'
                    else:
                        preview = preview_text
                    message_url = url_for('content.get_message', message_id=email.id)
            
            elif message.message_type.value == 'article':
                article = db_session.query(Article).get(message.id)
                if article and article.published:
                    type_specific_data = article
                    title = article.title
                    preview = article.processed_content[:200] + '...' if article.processed_content and len(article.processed_content) > 200 else article.processed_content
                    message_url = url_for('articles.view_article', slug=article.slug)
                    display_date = article.published_at or article.created_at
            
            elif message.message_type.value == 'widget':
                widget = db_session.query(ReactWidget).get(message.id)
                if widget:
                    type_specific_data = widget
                    title = widget.title
                    preview = widget.description or 'Interactive React widget'
                    message_url = url_for('widgets.view_widget', slug=widget.slug)
                    display_date = widget.published_at or widget.created_at
            
            elif message.message_type.value == 'quote':
                quote = db_session.query(Quote).get(message.id)
                if quote:
                    type_specific_data = quote
                    title = f"{quote.quote_type.title()}: {quote.text[:50]}..." if len(quote.text) > 50 else f"{quote.quote_type.title()}: {quote.text}"
                    preview = f"By {quote.original_author or 'Unknown'}" + (f" - {quote.commentary[:100]}..." if quote.commentary else "")
                    message_url = url_for('quotes.view_quote', quote_id=quote.id) + f"#{quote.id}"
            
            # Only include if we have the type-specific data and a URL
            if type_specific_data and message_url:
                display_messages.append({
                    'type': message.message_type.value,
                    'id': message.id,
                    'title': title,
                    'created_at': display_date,
                    'created_at_formatted': display_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'channel': message.channel,
                    'author': message.author,
                    'preview': preview,
                    'url': message_url,
                    'object': type_specific_data
                })
        
        # Calculate next page timestamp if there are more messages
        older_than_next_tsdate = None
        older_than_next_tstime = None
        
        if display_messages and has_more:
            # Format timestamp as YYYY-MM-DD and HHMMSS for URL
            dt = display_messages[-1]['created_at']
            older_than_next_tsdate = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
            older_than_next_tstime = f"{dt.hour:02d}{dt.minute:02d}{dt.second:02d}"
        
        return render_template(
            'all_messages.html',
            messages=display_messages,
            has_more=has_more,
            older_than_tsdate=older_than_next_tsdate,
            older_than_tstime=older_than_next_tstime,
            available_channels=allowed_channels
        )


@content_bp.route('/channel/<string:channel>/message_list')
@optional_auth
@navigable_per_channel(name="Message List",
                      description="List messages for a channel",
                      order=100)
def channel_list(channel: str) -> Response:
    """
    Display a paginated list of all messages (titles and dates) in a specific channel.
    
    :param channel: Name of the channel to list messages from
    :return: Rendered template response with message list
    """
    channel_manager = get_channel_manager()
    domain_manager = get_domain_manager()
    current_domain = g.current_domain
    
    # Check if channel exists
    config = channel_manager.get_channel_config(channel)
    if not config:
        return handle_error(
            "404",
            "Channel Not Found",
            f"Channel '{channel}' not found",
            f"No configuration for channel {channel}"
        )
        
    # Check domain access for channel
    if not domain_manager.is_channel_allowed(current_domain, channel):
        return handle_error(
            "404",
            "Channel Not Available",
            "This channel is not available on this domain.",
            f"Channel {channel} not allowed on domain {current_domain}"
        )
        
    # Check authentication if required
    if config.requires_auth and 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 100  # Number of messages per page
    
    with db.session() as db_session:
        # Count total messages in channel  
        total_count = db_session.query(Email).filter_by(channel=channel).count()
        
        # Get messages for current page
        messages = db_session.query(Email).filter_by(channel=channel)\
            .order_by(Email.created_at.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
            
        # Format timestamps
        for message in messages:
            message.created_at_formatted = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template(
            'channel_list.html',
            channel=channel,
            channel_config=config,
            messages=messages,
            total_count=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_prev=has_prev,
            has_next=has_next
        )