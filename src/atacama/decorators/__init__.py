"""Web decorators for authentication and navigation."""

from .auth import require_auth, optional_auth, require_admin
from .navigation import navigable, navigable_per_channel, get_navigation_items, get_navigable_routes, get_per_channel_routes

__all__ = [
    # Auth decorators
    'require_auth', 'optional_auth', 'require_admin',
    
    # Navigation decorators and functions
    'navigable', 'navigable_per_channel', 'get_navigation_items', 'get_navigable_routes', 'get_per_channel_routes'
]