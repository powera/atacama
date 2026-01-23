"""Navigation tracking and decorator utilities."""

import inspect
from functools import wraps
from typing import Dict, List, Callable, Any, Optional

# Store for registered navigable routes
# Structure: {blueprint_name: [{route_info}, {route_info}, ...]}
_navigable_routes: Dict[str, List[Dict[str, Any]]] = {}

# Store for per-channel navigable routes
_per_channel_routes: Dict[str, List[Dict[str, Any]]] = {}

def _detect_blueprint_name(route_func: Callable) -> str:
    """
    Detect the blueprint name from a Flask route function.
    
    This function inspects the route function to find blueprint information
    that was added by the @blueprint.route() decorator.
    
    :param route_func: The route function to inspect
    :return: Blueprint name if detected, otherwise module name
    """
    # Check if the function has blueprint information from Flask decorators
    if hasattr(route_func, '_blueprint_name'):
        return route_func._blueprint_name
    
    # Check if the function has a __self__ attribute (bound method)
    if hasattr(route_func, '__self__') and hasattr(route_func.__self__, 'name'):
        return route_func.__self__.name
    
    # Try to find blueprint info in the function's closure or attributes
    func = route_func
    while hasattr(func, '__wrapped__'):
        if hasattr(func, '_blueprint_name'):
            return func._blueprint_name
        func = func.__wrapped__
    
    # Look for blueprint in the function's globals
    if hasattr(route_func, '__globals__'):
        for name, obj in route_func.__globals__.items():
            if name.endswith('_bp') and hasattr(obj, 'name'):
                # Found a blueprint object, check if this function is registered to it
                # This is a heuristic - we assume the blueprint in the same module
                # is the one this function belongs to
                return obj.name
    
    # Fallback to module name
    return route_func.__module__.split('.')[-1]

def navigable(name: str, description: str = "", category: str = "main", 
              order: int = 100, requires_auth: Optional[bool] = None, 
              requires_admin: bool = False, blueprint: Optional[str] = None) -> Callable:
    """
    Decorator to mark a route as navigable and include it in the site navigation.
    
    :param name: Display name for the navigation link
    :param description: Description of the route
    :param category: Navigation category ("main", "channels", "admin", "user", etc.)
    :param order: Sort order within the category (lower numbers appear first)
    :param requires_auth: Whether this route requires authentication (auto-detected if None)
    :param requires_admin: Whether this route requires admin privileges
    :param blueprint: Override blueprint name (if different from module name)
    :return: Decorated route function
    """
    def decorator(route_func: Callable) -> Callable:
        # Get the blueprint name - use override if provided, otherwise detect from route decorator
        blueprint_name = blueprint if blueprint else _detect_blueprint_name(route_func)
        
        # Store the original endpoint name
        endpoint = f"{blueprint_name}.{route_func.__name__}"
        
        # Auto-detect authentication requirements if not specified
        needs_auth = requires_auth
        if needs_auth is None:
            # Check if the function or any wrapper has '__auth_required__' attribute
            # or if the function name is 'decorated_function' from require_auth
            # or if the function's closure contains 'require_auth'
            func = route_func
            while hasattr(func, '__wrapped__'):
                if (hasattr(func, '__auth_required__') or 
                    func.__name__ == 'decorated_function'):
                    needs_auth = True
                    break
                func = func.__wrapped__
            
            # If we still can't determine, check the source code or module
            if needs_auth is None:
                # Default to False if we can't determine
                needs_auth = False
                
                # Try to check if it's wrapped with require_auth from source inspection
                try:
                    source = inspect.getsource(route_func)
                    if "@require_auth" in source:
                        needs_auth = True
                except (IOError, TypeError):
                    pass
        
        # Register this route to our navigable routes store
        if blueprint_name not in _navigable_routes:
            _navigable_routes[blueprint_name] = []
            
        _navigable_routes[blueprint_name].append({
            'endpoint': endpoint,
            'name': name,
            'description': description,
            'category': category,
            'order': order,
            'requires_auth': needs_auth,
            'requires_admin': requires_admin,
            'view_func': route_func.__name__
        })
        
        @wraps(route_func)
        def wrapped_func(*args: Any, **kwargs: Any) -> Any:
            return route_func(*args, **kwargs)
            
        return wrapped_func
        
    return decorator

def navigable_per_channel(name: str, description: str = "", 
                         channel_param: str = "channel",
                         order: int = 100, 
                         requires_auth: Optional[bool] = None, 
                         requires_admin: bool = False) -> Callable:
    """
    Decorator to mark a route as navigable per-channel.
    These routes will appear in the navigation for each accessible channel.
    
    :param name: Display name for the navigation link
    :param description: Description of the route
    :param channel_param: Name of the channel parameter in the route (default: "channel")
    :param order: Sort order within channel navigation (lower numbers appear first)
    :param requires_auth: Whether this route requires authentication (auto-detected if None)
    :param requires_admin: Whether this route requires admin privileges
    :return: Decorated route function
    """
    def decorator(route_func: Callable) -> Callable:
        # Get the blueprint name - detect from route decorator
        blueprint_name = _detect_blueprint_name(route_func)
        
        # Store the original endpoint name
        endpoint = f"{blueprint_name}.{route_func.__name__}"
        
        # Auto-detect authentication requirements if not specified
        needs_auth = requires_auth
        if needs_auth is None:
            # Use same auto-detection logic as navigable
            func = route_func
            while hasattr(func, '__wrapped__'):
                if (hasattr(func, '__auth_required__') or 
                    func.__name__ == 'decorated_function'):
                    needs_auth = True
                    break
                func = func.__wrapped__
            
            if needs_auth is None:
                needs_auth = False
                
                try:
                    source = inspect.getsource(route_func)
                    if "@require_auth" in source:
                        needs_auth = True
                except (IOError, TypeError):
                    pass
        
        # Register this route to our per-channel routes store
        if blueprint_name not in _per_channel_routes:
            _per_channel_routes[blueprint_name] = []
            
        _per_channel_routes[blueprint_name].append({
            'endpoint': endpoint,
            'name': name,
            'description': description,
            'channel_param': channel_param,
            'order': order,
            'requires_auth': needs_auth,
            'requires_admin': requires_admin,
            'view_func': route_func.__name__
        })
        
        @wraps(route_func)
        def wrapped_func(*args: Any, **kwargs: Any) -> Any:
            return route_func(*args, **kwargs)
            
        return wrapped_func
        
    return decorator

def get_navigable_routes() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all registered navigable routes.
    
    :return: Dictionary of navigable route information by category
    """
    return _navigable_routes

def get_per_channel_routes() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all registered per-channel navigable routes.
    
    :return: Dictionary of per-channel route information by blueprint
    """
    return _per_channel_routes

def get_navigation_items(user: Optional[Any] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get navigation items organized by category, filtered by user permissions.
    
    :param user: Current user object for permission checking
    :return: Dictionary of navigation items by category
    """
    from flask import url_for
    
    # Initialize navigation structure
    nav_items: Dict[str, List[Dict[str, Any]]] = {
        'main': [],
        'channels': [],
        'admin': [],
        'user': [],
        'per_channel': []  # Routes that should be shown for each channel
    }
    
    # Build navigation from registered routes
    for blueprint, routes in _navigable_routes.items():
        for route in routes:
            # Skip items requiring auth if no user
            if route['requires_auth'] and user is None:
                continue
                
            # Skip admin routes if user has no admin access
            if route['requires_admin'] and (user is None or not hasattr(user, 'admin_channel_access') or 
                                          not user.admin_channel_access):
                continue
            
            category = route['category']
            # Ensure category exists
            if category not in nav_items:
                nav_items[category] = []
                
            nav_items[category].append({
                'name': route['name'],
                'description': route['description'],
                'url': url_for(route['endpoint']),
                'order': route['order']
            })
    
    # Add per-channel routes
    for blueprint, routes in _per_channel_routes.items():
        for route in routes:
            # Skip items requiring auth if no user
            if route['requires_auth'] and user is None:
                continue
                
            # Skip admin routes if user has no admin access
            if route['requires_admin'] and (user is None or not hasattr(user, 'admin_channel_access') or 
                                          not user.admin_channel_access):
                continue
                
            nav_items['per_channel'].append({
                'name': route['name'],
                'description': route['description'],
                'endpoint': route['endpoint'],
                'channel_param': route['channel_param'],
                'order': route['order']
            })
    
    # Sort each category by order
    for category in nav_items:
        nav_items[category] = sorted(nav_items[category], key=lambda x: x.get('order', 100))
        
    return nav_items