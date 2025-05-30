"""Blueprint for serving Lithuanian language learning resources."""

import os
import random
import re
from typing import Dict, List, Optional, Union, Any

from flask import Blueprint, send_file, request, abort, Response, jsonify

import constants  # for LITHUANIAN_AUDIO_DIR
from common.base.logging_config import get_logger
from data.trakaido.wordlists import get_all_word_pairs_flat, all_words

logger = get_logger(__name__)

trakaido_bp = Blueprint('trakaido', __name__)

LITHUANIAN_CHARS = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž"


@trakaido_bp.route('/api/lithuanian')
def lithuanian_api_index() -> Response:
    """
    Provide an overview of the Lithuanian API endpoints.
    
    :return: JSON response with API information
    """
    api_info = {
        "name": "Lithuanian Language Learning API",
        "version": "1.0.0",
        "endpoints": {
            "wordlists": {
                "GET /api/lithuanian/wordlists": "List all wordlist corpora",
                "GET /api/lithuanian/wordlists/_all": "Get all words from all corpora",
                "GET /api/lithuanian/wordlists/search": "Search for words (params: english, lithuanian, corpus, group)",
                "GET /api/lithuanian/wordlists/{corpus}": "List all groups in a corpus in a nested structure",
                "GET /api/lithuanian/wordlists/{corpus}?group={group_name}": "Get words for a specific group in a corpus"
            },
            "audio": {
                "GET /api/lithuanian/audio/voices": "List all available voices",
                "GET /api/lithuanian/audio/{word}": "Get audio for a Lithuanian word (param: voice)"
            }
        }
    }
    return jsonify(api_info)


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
        
        word_filename = sanitize_lithuanian_word(word)

        # Construct the file path
        file_path = os.path.join(constants.LITHUANIAN_AUDIO_DIR, selected_voice, f"{word_filename}.mp3")
        
        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return None
        
        return file_path
    except Exception as e:
        logger.error(f"Error getting audio file path for word '{word}': {str(e)}")
        return None

# Wordlist related functions
def get_wordlist_corpora() -> List[str]:
    """
    Get a list of all wordlist corpora.
    
    :return: List of corpus names
    """
    try:
        corpora = list(all_words.keys())
        logger.debug(f"Found {len(corpora)} wordlist corpora: {', '.join(corpora)}")
        return corpora
    except Exception as e:
        logger.error(f"Error getting wordlist corpora: {str(e)}")
        return []

def get_groups(corpus: str) -> List[str]:
    """
    Get a list of groups for a given corpus.
    
    :param corpus: The corpus name
    :return: List of group names
    """
    try:
        if corpus not in all_words:
            logger.error(f"Corpus not found: {corpus}")
            return []
        
        groups = list(all_words[corpus].keys())
        logger.debug(f"Found {len(groups)} groups for {corpus}: {', '.join(groups)}")
        return groups
    except Exception as e:
        logger.error(f"Error getting groups for {corpus}: {str(e)}")
        return []

def get_words_by_corpus(corpus: str, group: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get words for a specific corpus and optional group.
    
    :param corpus: The corpus name
    :param group: Optional group name
    :return: List of word pairs
    """
    try:
        if corpus not in all_words:
            logger.error(f"Corpus not found: {corpus}")
            return []
        
        if group:
            if group not in all_words[corpus]:
                logger.error(f"Group {group} not found in corpus {corpus}")
                return []
            return all_words[corpus][group]
        
        # If no group specified, return all words from all groups in this corpus
        result = []
        for grp, words in all_words[corpus].items():
            result.extend(words)
        return result
    except Exception as e:
        logger.error(f"Error getting words for corpus {corpus}, group {group}: {str(e)}")
        return []

# API Routes for wordlists
@trakaido_bp.route('/api/lithuanian/wordlists')
def list_wordlist_corpora() -> Union[Response, tuple]:
    """
    List all available wordlist corpora.
    
    :return: JSON response with list of corpora
    """
    try:
        corpora = get_wordlist_corpora()
        return jsonify({"corpora": corpora})
    except Exception as e:
        logger.error(f"Error listing wordlist corpora: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/search')
def search_words() -> Union[Response, tuple]:
    """
    Search for words in the wordlists.
    
    Query parameters:
    - english: Search term for English words
    - lithuanian: Search term for Lithuanian words
    - corpus: Filter by corpus
    - group: Filter by group (requires corpus)
    
    :return: JSON response with matching words
    """
    try:
        english_term = request.args.get('english', '').lower()
        lithuanian_term = request.args.get('lithuanian', '').lower()
        corpus = request.args.get('corpus')
        group = request.args.get('group')
        
        if not english_term and not lithuanian_term:
            return jsonify({"error": "At least one search term (english or lithuanian) is required"}), 400
        
        # Get all words or filtered by corpus/group
        if corpus:
            words = get_words_by_corpus(corpus, group)
        else:
            words = get_all_word_pairs_flat()
        
        # Filter by search terms
        results = []
        for word in words:
            english_match = not english_term or english_term in word['english'].lower()
            lithuanian_match = not lithuanian_term or lithuanian_term in word['lithuanian'].lower()
            
            if english_match and lithuanian_match:
                results.append(word)
        
        return jsonify({
            "query": {
                "english": english_term,
                "lithuanian": lithuanian_term,
                "corpus": corpus,
                "group": group
            },
            "results": results,
            "count": len(results)
        })
    except Exception as e:
        logger.error(f"Error searching words: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/<corpus>')
def list_groups_in_corpus(corpus: str) -> Union[Response, tuple]:
    """
    List all groups in a corpus in a nested structure, or return words for a specific group.
    
    :param corpus: The corpus name
    :return: JSON response with groups in a nested structure or words for a specific group
    """
    try:
        groups = get_groups(corpus)
        if not groups:
            return jsonify({"error": f"Corpus '{corpus}' not found"}), 404
        
        # Check if a specific group is requested via query parameter
        requested_group = request.args.get('group')
        
        if requested_group:
            # Return words for the specific group
            words = get_words_by_corpus(corpus, requested_group)
            if not words:
                return jsonify({"error": f"Group '{requested_group}' not found in corpus '{corpus}'"}), 404
            
            return jsonify({
                "corpus": corpus,
                "group": requested_group,
                "words": words
            })
        
        # Return all groups in a nested structure
        result = {
            "corpus": corpus,
            "groups": {}
        }
        
        # Create a nested structure with group names and their words
        for group_name in groups:
            result["groups"][group_name] = all_words[corpus][group_name]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error listing groups for {corpus}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/_all')
def get_all_words() -> Union[Response, tuple]:
    """
    Get all words from all corpora and groups.
    
    :return: JSON response with all words
    """
    try:
        words = get_all_word_pairs_flat()
        return jsonify({"words": words})
    except Exception as e:
        logger.error(f"Error getting all words: {str(e)}")
        return jsonify({"error": str(e)}), 500

# API Routes for audio
@trakaido_bp.route('/api/lithuanian/audio/voices')
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

@trakaido_bp.route('/api/lithuanian/audio/<word>')
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