"""Blueprint for handling site navigation."""

import json
from flask import Blueprint, render_template, url_for, g
from sqlalchemy.orm import joinedload

from common.auth import require_auth
from common.channel_config import get_channel_manager
from common.messages import check_channel_access

from common.logging_config import get_logger
logger = get_logger(__name__)

nav_bp = Blueprint('nav', __name__)

@nav_bp.route('/nav')
@require_auth
def navigation() -> str:
    """
    Show site navigation/sitemap page.
    
    :return: Rendered template response
    """
    channel_manager = get_channel_manager()
    
    # Build navigation structure
    nav_items = {
        'main': [],
        'channels': [],
        'admin': [],
        'user': []
    }

    # Main navigation items
    nav_items['main'] = [
        {
            'name': 'Home',
            'description': 'Service information and recent messages',
            'url': url_for('content.landing_page')
        },
        {
            'name': 'All Messages',
            'description': 'View the full message stream',
            'url': url_for('content.message_stream')
        },
        {
            'name': 'All Articles',
            'description': 'View published articles',
            'url': url_for('articles.article_stream', channel='public')
        },
        {
            'name': 'Quote Archive',
            'description': 'Browse all tracked quotes',
            'url': url_for('quotes.list_quotes')
        }
    ]
    
    # Get accessible channels
    for channel in channel_manager.channels:
        config = channel_manager.get_channel_config(channel)
        if config and check_channel_access(channel, g.user):
            nav_items['channels'].append({
                'name': channel,
                'config': config,
                'links': [
                    {
                        'name': f'{channel} Messages',
                        'url': url_for('content.message_stream', channel=channel)
                    },
                    {
                        'name': f'{channel} Articles',
                        'url': url_for('articles.article_stream', channel=channel)
                    }
                ]
            })
    
    # Add user-specific pages if authenticated
    if g.user:
        nav_items['user'] = [
            {
                'name': 'Channel Preferences',
                'description': 'Manage your channel subscriptions',
                'url': url_for('content.channel_preferences')
            },
            {
                'name': 'Submit Message',
                'description': 'Create a new message',
                'url': url_for('submit.show_submit_form')
            },
            {
                'name': 'Submit Article',
                'description': 'Create a new article',
                'url': url_for('articles.submit_article')
            },
            {
                'name': 'Draft Articles',
                'description': 'View and edit your unpublished articles',
                'url': url_for('articles.list_drafts')
            }
        ]
        
        # Add admin pages if user has admin access
        admin_channels = json.loads(g.user.admin_channel_access or '{}')
        if admin_channels:
            nav_items['admin'] = [
                {
                    'name': 'Admin Dashboard',
                    'description': 'Manage users and permissions',
                    'url': url_for('admin.list_users')
                }
            ]
            nav_items['main'].extend([
                {
                    'name': 'System Status',
                    'description': 'View system metrics and diagnostics',
                    'url': url_for('debug.debug_info'),
                },
            ])
    
    return render_template(
        'nav.html',
        nav_items=nav_items,
        user=g.user
    )
