"""Audio API handlers for multi-language learning."""

# Standard library imports
import os
import random
from typing import List, Optional, Union

# Third-party imports
from flask import Response, abort, g, jsonify, request, send_file

# Local application imports
import constants
from common.config.language_config import get_language_manager
from .shared import LITHUANIAN_CHARS, logger, sanitize_lithuanian_word, trakaido_bp


##############################################################################

# API Documentation for audio endpoints
AUDIO_API_DOCS = {
    "GET /api/audio/voices": "List all available voices for current language (subdomain)",
    "GET /api/audio/{word}": "Get audio for a word in current language (subdomain) (param: voice)",
    "GET /api/lithuanian/audio/voices": "List all available voices for Lithuanian (legacy)",
    "GET /api/lithuanian/audio/{word}": "Get audio for a Lithuanian word (param: voice) (legacy)",
    "GET /api/{language}/audio/voices": "List all available voices for specific language",
    "GET /api/{language}/audio/{word}": "Get audio for a word in specific language (param: voice)"
}

def get_available_voices(audio_dir: Optional[str] = None) -> List[str]:
    """
    Get a list of available voice directories for a language.

    :param audio_dir: Optional audio directory path, defaults to current language's directory
    :return: List of voice names (directory names)
    """
    try:
        # Use provided directory or fall back to current language's directory
        if audio_dir is None:
            if hasattr(g, 'language_config'):
                audio_dir = g.language_config.get_audio_dir()
            else:
                audio_dir = constants.LITHUANIAN_AUDIO_DIR

        if not os.path.exists(audio_dir):
            logger.error(f"Audio directory not found: {audio_dir}")
            return []

        # Get all directories in the audio directory
        voices = [d for d in os.listdir(audio_dir)
                 if os.path.isdir(os.path.join(audio_dir, d))]

        return voices
    except Exception as e:
        logger.error(f"Error getting voice directories from {audio_dir}: {str(e)}")
        return []


def sanitize_word_for_audio(word: str, character_set: Optional[str] = None) -> str:
    """
    Sanitize a word for use in audio file names.

    :param word: Word to sanitize
    :param character_set: Optional character set for the language, if None all chars are allowed
    :return: Sanitized word suitable for filename
    """
    if character_set:
        # If character set is provided, use the existing sanitize_lithuanian_word logic
        return sanitize_lithuanian_word(word, character_set)
    else:
        # For languages without character sets (Chinese, Korean), just remove slashes and nulls
        return word.replace('/', '').replace('\0', '').lower()


def get_audio_file_path(word: str, voice: Optional[str] = None, audio_dir: Optional[str] = None, character_set: Optional[str] = None) -> Optional[str]:
    """
    Get the path to an audio file for the given word and voice.

    :param word: Word to get audio for
    :param voice: Optional voice name to use, if None a random voice will be selected
    :param audio_dir: Optional audio directory path, defaults to current language's directory
    :param character_set: Optional character set for sanitization
    :return: Path to the audio file or None if not found
    """
    try:
        # Use provided directory or fall back to current language's directory
        if audio_dir is None:
            if hasattr(g, 'language_config'):
                audio_dir = g.language_config.get_audio_dir()
                character_set = g.language_config.character_set if character_set is None else character_set
            else:
                audio_dir = constants.LITHUANIAN_AUDIO_DIR
                character_set = LITHUANIAN_CHARS if character_set is None else character_set

        voices = get_available_voices(audio_dir)
        if not voices:
            logger.error(f"No voice directories found in {audio_dir}")
            return None

        # If no voice specified, choose a random one
        selected_voice = voice if voice in voices else random.choice(voices)

        word_filename = sanitize_word_for_audio(word, character_set)

        # Construct the file path
        file_path = os.path.join(audio_dir, selected_voice, f"{word_filename}.mp3")

        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return None

        return file_path
    except Exception as e:
        logger.error(f"Error getting audio file path for word '{word}': {str(e)}")
        return None


# API Routes for audio

# Generic audio endpoints (use current language from subdomain)
@trakaido_bp.route('/api/audio/voices')
def list_voices_current() -> Union[Response, tuple]:
    """
    List all available voices for the current language (determined by subdomain).

    :return: JSON response with list of voices
    """
    try:
        voices = get_available_voices()
        language_name = g.language_config.name if hasattr(g, 'language_config') else "Lithuanian"
        return jsonify({"voices": voices, "language": language_name})
    except Exception as e:
        logger.error(f"Error listing voices for current language: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/audio/<word>')
def serve_audio_current(word: str) -> Union[Response, tuple]:
    """
    Serve an audio file for the given word in the current language (determined by subdomain).

    :param word: Word to get audio for
    :return: Audio file response or error
    """
    try:
        # Get the voice parameter from the request, if provided
        voice = request.args.get('voice')

        # Get the audio file path using current language
        file_path = get_audio_file_path(word, voice)
        if not file_path:
            language_name = g.language_config.name if hasattr(g, 'language_config') else "Lithuanian"
            return abort(404, f"Audio for '{word}' not found in {language_name}")

        # Serve the audio file
        return send_file(file_path, mimetype='audio/mpeg')
    except Exception as e:
        logger.error(f"Error serving audio for word '{word}' in current language: {str(e)}")
        return jsonify({"error": str(e)}), 500


# Language-specific audio endpoints
@trakaido_bp.route('/api/<language>/audio/voices')
def list_voices_language(language: str) -> Union[Response, tuple]:
    """
    List all available voices for a specific language.

    :param language: Language key (e.g., 'lithuanian', 'chinese', 'korean', 'french')
    :return: JSON response with list of voices
    """
    try:
        language_manager = get_language_manager()
        language_config = language_manager.get_language_config(language)
        audio_dir = language_config.get_audio_dir()

        voices = get_available_voices(audio_dir)
        return jsonify({"voices": voices, "language": language_config.name})
    except Exception as e:
        logger.error(f"Error listing voices for language '{language}': {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/<language>/audio/<word>')
def serve_audio_language(language: str, word: str) -> Union[Response, tuple]:
    """
    Serve an audio file for the given word in a specific language.

    :param language: Language key (e.g., 'lithuanian', 'chinese', 'korean', 'french')
    :param word: Word to get audio for
    :return: Audio file response or error
    """
    try:
        # Get the voice parameter from the request, if provided
        voice = request.args.get('voice')

        language_manager = get_language_manager()
        language_config = language_manager.get_language_config(language)
        audio_dir = language_config.get_audio_dir()
        character_set = language_config.character_set

        # Get the audio file path for the specific language
        file_path = get_audio_file_path(word, voice, audio_dir, character_set)
        if not file_path:
            return abort(404, f"Audio for '{word}' not found in {language_config.name}")

        # Serve the audio file
        return send_file(file_path, mimetype='audio/mpeg')
    except Exception as e:
        logger.error(f"Error serving audio for word '{word}' in language '{language}': {str(e)}")
        return jsonify({"error": str(e)}), 500
