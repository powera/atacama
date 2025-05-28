"""Blueprint for serving Lithuanian audio files."""

import os
import random
from typing import List, Optional, Union

from flask import Blueprint, send_file, request, abort, Response, jsonify

import constants  # for LITHUANIAN_AUDIO_DIR
from common.base.logging_config import get_logger

logger = get_logger(__name__)

lithuanian_audio_bp = Blueprint('lithuanian_audio', __name__)


def get_available_voices() -> List[str]:
    """
    Get a list of available voice directories.
    
    :return: List of voice names (directory names)
    """
    try:
        if not os.path.exists(constants.LITHUANIAN_AUDIO_DIR):
            logger.error(f"Lithuanian audio directory not found: {constants.LITHUANIAN_AUDIO_DIR}")
            return []
        
        # Get all directories in the Lithuanian audio directory
        voices = [d for d in os.listdir(constants.LITHUANIAN_AUDIO_DIR) 
                 if os.path.isdir(os.path.join(constants.LITHUANIAN_AUDIO_DIR, d))]
        
        logger.debug(f"Found {len(voices)} Lithuanian voice directories: {', '.join(voices)}")
        return voices
    except Exception as e:
        logger.error(f"Error getting Lithuanian voice directories: {str(e)}")
        return []

def get_audio_file_path(word: str, voice: Optional[str] = None) -> Optional[str]:
    """
    Get the path to an audio file for the given word and voice.
    
    :param word: Lithuanian word to get audio for
    :param voice: Optional voice name to use, if None a random voice will be selected
    :return: Path to the audio file or None if not found
    """
    try:
        voices = get_available_voices()
        if not voices:
            logger.error("No Lithuanian voice directories found")
            return None
        
        # If no voice specified, choose a random one
        selected_voice = voice if voice in voices else random.choice(voices)
        
        # Construct the file path
        file_path = os.path.join(constants.LITHUANIAN_AUDIO_DIR, selected_voice, f"{word}.mp3")
        
        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return None
        
        return file_path
    except Exception as e:
        logger.error(f"Error getting audio file path for word '{word}': {str(e)}")
        return None

@lithuanian_audio_bp.route('/api/lithuanian/<word>')
def serve_lithuanian_audio(word: str) -> Union[Response, tuple]:
    """
    Serve a Lithuanian audio file for the given word.
    
    :param word: Lithuanian word to get audio for
    :return: Audio file response or error
    """
    try:
        # Get the voice parameter from the request, if provided
        voice = request.args.get('voice')
        
        # Get the audio file path
        file_path = get_audio_file_path(word, voice)
        if not file_path:
            return abort(404, f"Audio for '{word}' not found")
        
        # Serve the audio file
        return send_file(file_path, mimetype='audio/mpeg')
    except Exception as e:
        logger.error(f"Error serving Lithuanian audio for word '{word}': {str(e)}")
        return jsonify({"error": str(e)}), 500

@lithuanian_audio_bp.route('/api/lithuanian/voices')
def list_voices() -> Union[Response, tuple]:
    """
    List all available Lithuanian voices.
    
    :return: JSON response with list of voices
    """
    try:
        voices = get_available_voices()
        return jsonify({"voices": voices})
    except Exception as e:
        logger.error(f"Error listing Lithuanian voices: {str(e)}")
        return jsonify({"error": str(e)}), 500