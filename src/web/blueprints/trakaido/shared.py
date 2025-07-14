"""Shared data and utilities for the Trakaido Lithuanian language learning module."""

import re
from flask import Blueprint
from common.base.logging_config import get_logger

# Create the blueprint that will be used by all trakaido modules
trakaido_bp = Blueprint('trakaido', __name__)

# Lithuanian character set for validation and sanitization
LITHUANIAN_CHARS = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"

# Production path for the Trakaido React app
TRAKAIDO_PATH_PROD = "/home/atacama/trakaido_react/build/index.html"

# Shared logger
logger = get_logger(__name__)


def sanitize_lithuanian_word(word: str) -> str:
    """
    Sanitize a Lithuanian word or phrase for use as a filename.
    
    Args:
        word: The Lithuanian word or phrase to sanitize
    
    Returns:
        Sanitized filename-safe version or empty string if invalid
    """
    word = word.strip().lower()
    
    # Replace spaces with underscores for multi-word phrases
    word_with_underscores = word.replace(' ', '_')
    
    # Allow all Lithuanian letters, basic Latin letters, and safe characters
    sanitized = re.sub(r'[^a-z' + LITHUANIAN_CHARS + r'\-_]', '', word_with_underscores)
    
    if not sanitized or len(sanitized) > 100:
        return ""
        
    return sanitized