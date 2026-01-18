"""Trakaido Lithuanian language learning blueprint package."""

# Local application imports
from trakaido.blueprints import shared  # Shared utils imported first

# Import modules for side effects (registering routes on trakaido_bp)
# These modules are imported to register their routes, not to use their names directly
from trakaido.blueprints import trakaido_tools
from trakaido.blueprints import userconfig_v2
from trakaido.blueprints import userstats

__all__ = [
    'trakaido_bp',
    'trakaido_tools',
    'userconfig_v2',
    'userstats',
]

# Export the blueprint
trakaido_bp = shared.trakaido_bp

# Reference side-effect imports to satisfy static analysis
_side_effect_modules = (trakaido_tools, userconfig_v2, userstats)