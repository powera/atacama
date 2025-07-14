from . import shared
from . import trakaido_tools
from . import audio
from . import wordlists

__all__ = [
    'trakaido_bp'
]

# Export the blueprint
trakaido_bp = shared.trakaido_bp