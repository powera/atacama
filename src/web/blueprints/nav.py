"""Blueprint for handling site navigation."""

import json
from flask import Blueprint, render_template, url_for, g
from sqlalchemy.orm import joinedload

from common.auth import require_auth
from common.channel_config import get_channel_manager
from common.messages import check_channel_access
from common.navigation import get_navigation_items

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
    
    # Get registered navigation items
    nav_items = get_navigation_items(g.user)
    
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
    
    return render_template(
        'nav.html',
        nav_items=nav_items,
        user=g.user
    )
