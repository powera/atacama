"""Blog functionality blueprint package."""

# Import shared blueprints (this will register all routes from individual files)
from .shared import content_bp, quotes_bp, feeds_bp, statistics_bp, widgets_bp

# Import individual modules to register their routes with the shared blueprints
from . import content
from . import article  
from . import submit
from . import quotes
from . import feeds
from . import statistics
from . import widgets

# Export all blueprints for easy importing
__all__ = [
    'content_bp',
    'quotes_bp', 
    'feeds_bp',
    'statistics_bp',
    'widgets_bp'
]

# Convenience list for bulk registration
BLOG_BLUEPRINTS = [
    content_bp,
    quotes_bp,
    feeds_bp,
    statistics_bp,
    widgets_bp
]