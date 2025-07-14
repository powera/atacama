"""Blueprint for handling site navigation."""

import json
from flask import Blueprint, render_template, url_for, g
from sqlalchemy.orm import joinedload

from web.decorators import require_auth, get_navigation_items
from common.config.channel_config import get_channel_manager
from models.messages import check_channel_access
from common.base.logging_config import get_logger
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
    
    # Build channel navigation using per-channel routes
    channel_nav = []
    per_channel_routes = nav_items.get('per_channel', [])
    
    for channel_name in sorted(channel_manager.get_channel_names()):
        config = channel_manager.get_channel_config(channel_name)
        if config and check_channel_access(channel_name, g.user):
            display_name = channel_manager.get_display_name(channel_name)
            channel_item = {
                'name': display_name,
                'channel': channel_name,
                'description': config.description,
                'links': []
            }
            
            # Add per-channel routes
            for route in per_channel_routes:
                try:
                    # Build URL with channel parameter
                    route_kwargs = {route['channel_param']: channel_name}
                    link_url = url_for(route['endpoint'], **route_kwargs)
                    
                    channel_item['links'].append({
                        'name': route['name'],
                        'url': link_url,
                        'description': route['description'],
                        'order': route['order']
                    })
                except Exception as e:
                    # Route might not be available for this channel
                    logger.debug(f"Could not generate URL for {route['endpoint']} with channel {channel_name}: {e}")
                    
            # Sort links by order
            channel_item['links'].sort(key=lambda x: x.get('order', 100))
                
            channel_nav.append(channel_item)
    
    # Add channel navigation to the items
    nav_items['channel_nav'] = channel_nav
    
    return render_template(
        'nav.html',
        nav_items=nav_items,
        user=g.user
    )