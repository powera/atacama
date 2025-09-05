"""Shared data and utilities for the Trakaido Lithuanian language learning module."""

# Standard library imports
import os
import re
from typing import Dict, List, Optional, Union

# Third-party imports
from flask import Blueprint, Response, send_file

# Local application imports
import constants
from common.base.logging_config import get_logger

# Create the blueprint that will be used by all trakaido modules
trakaido_bp = Blueprint('trakaido', __name__)

# Lithuanian character set for validation and sanitization
LITHUANIAN_CHARS = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"

# Production path for the Trakaido React app
TRAKAIDO_PATH_PROD = "/home/trakaido/trakaido/build/index.html"

# Shared logger
logger = get_logger(__name__)

# Serve the Trakaido app from "/"
@trakaido_bp.route("/")
def trakaido_index() -> Response:
    """Serve the Trakaido single-page application."""
    TRAKAIDO_PATH_PROD = "/home/trakaido/trakaido/build/index.html"
    if os.path.exists(TRAKAIDO_PATH_PROD):
        # In production, serve the compiled index.html from the Trakaido repo
        return send_file(TRAKAIDO_PATH_PROD)


# Serve images from the Trakaido build directory
@trakaido_bp.route("/images/<path:filename>")
def trakaido_images(filename: str) -> Response:
    """Serve images from the Trakaido build directory."""
    images_dir = "/home/trakaido/trakaido/build/images"
    image_path = os.path.join(images_dir, filename)
    
    # Security check: ensure the path is within the images directory
    if not os.path.abspath(image_path).startswith(os.path.abspath(images_dir)):
        logger.warning(f"Attempted path traversal attack: {filename}")
        return Response("Forbidden", status=403)
    
    if os.path.exists(image_path) and os.path.isfile(image_path):
        return send_file(image_path)
    else:
        logger.warning(f"Image not found: {image_path}")
        return Response("Image not found", status=404)


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


def ensure_user_data_dir(user_id: str) -> str:
    """
    Ensure the user's data directory exists.
    
    :param user_id: The user's database ID
    :return: Path to the user's data directory
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir