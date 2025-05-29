"""Blueprint for serving Lithuanian language learning resources."""

import os
import random
from typing import Dict, List, Optional, Union, Any

from flask import Blueprint, send_file, request, abort, Response, jsonify

import constants  # for LITHUANIAN_AUDIO_DIR
from common.base.logging_config import get_logger
from data.trakaido.wordlists import get_all_word_pairs_flat, all_words

logger = get_logger(__name__)

trakaido_bp = Blueprint('trakaido', __name__)

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
                "GET /api/lithuanian/wordlists": "List all wordlist categories",
                "GET /api/lithuanian/wordlists/_all": "Get all words from all categories",
                "GET /api/lithuanian/wordlists/search": "Search for words (params: english, lithuanian, category, subcategory)",
                "GET /api/lithuanian/wordlists/{category}": "List subcategories or all words in a category (param: words=true)",
                "GET /api/lithuanian/wordlists/{category}/{subcategory}": "Get words for a specific subcategory"
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

# Wordlist related functions
def get_wordlist_categories() -> List[str]:
    """
    Get a list of all wordlist categories.
    
    :return: List of category names
    """
    try:
        categories = list(all_words.keys())
        logger.debug(f"Found {len(categories)} wordlist categories: {', '.join(categories)}")
        return categories
    except Exception as e:
        logger.error(f"Error getting wordlist categories: {str(e)}")
        return []

def get_subcategories(category: str) -> List[str]:
    """
    Get a list of subcategories for a given category.
    
    :param category: The category name
    :return: List of subcategory names
    """
    try:
        if category not in all_words:
            logger.error(f"Category not found: {category}")
            return []
        
        subcategories = list(all_words[category].keys())
        logger.debug(f"Found {len(subcategories)} subcategories for {category}: {', '.join(subcategories)}")
        return subcategories
    except Exception as e:
        logger.error(f"Error getting subcategories for {category}: {str(e)}")
        return []

def get_words_by_category(category: str, subcategory: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get words for a specific category and optional subcategory.
    
    :param category: The category name
    :param subcategory: Optional subcategory name
    :return: List of word pairs
    """
    try:
        if category not in all_words:
            logger.error(f"Category not found: {category}")
            return []
        
        if subcategory:
            if subcategory not in all_words[category]:
                logger.error(f"Subcategory {subcategory} not found in category {category}")
                return []
            return all_words[category][subcategory]
        
        # If no subcategory specified, return all words from all subcategories in this category
        result = []
        for sub, words in all_words[category].items():
            result.extend(words)
        return result
    except Exception as e:
        logger.error(f"Error getting words for category {category}, subcategory {subcategory}: {str(e)}")
        return []

# API Routes for wordlists
@trakaido_bp.route('/api/lithuanian/wordlists')
def list_wordlist_categories() -> Union[Response, tuple]:
    """
    List all available wordlist categories.
    
    :return: JSON response with list of categories
    """
    try:
        categories = get_wordlist_categories()
        return jsonify({"categories": categories})
    except Exception as e:
        logger.error(f"Error listing wordlist categories: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/search')
def search_words() -> Union[Response, tuple]:
    """
    Search for words in the wordlists.
    
    Query parameters:
    - english: Search term for English words
    - lithuanian: Search term for Lithuanian words
    - category: Filter by category
    - subcategory: Filter by subcategory (requires category)
    
    :return: JSON response with matching words
    """
    try:
        english_term = request.args.get('english', '').lower()
        lithuanian_term = request.args.get('lithuanian', '').lower()
        category = request.args.get('category')
        subcategory = request.args.get('subcategory')
        
        if not english_term and not lithuanian_term:
            return jsonify({"error": "At least one search term (english or lithuanian) is required"}), 400
        
        # Get all words or filtered by category/subcategory
        if category:
            words = get_words_by_category(category, subcategory)
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
                "category": category,
                "subcategory": subcategory
            },
            "results": results,
            "count": len(results)
        })
    except Exception as e:
        logger.error(f"Error searching words: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/<category>')
def list_subcategories_or_words(category: str) -> Union[Response, tuple]:
    """
    List subcategories for a category or all words if no subcategories exist.
    
    :param category: The category name
    :return: JSON response with subcategories or words
    """
    try:
        subcategories = get_subcategories(category)
        if not subcategories:
            return jsonify({"error": f"Category '{category}' not found"}), 404
        
        # Check if we should return words instead of subcategories
        all_words_param = request.args.get('words', 'false').lower() == 'true'
        
        if all_words_param:
            words = get_words_by_category(category)
            return jsonify({"category": category, "words": words})
        
        return jsonify({"category": category, "subcategories": subcategories})
    except Exception as e:
        logger.error(f"Error listing subcategories for {category}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/<category>/<subcategory>')
def get_words_for_subcategory(category: str, subcategory: str) -> Union[Response, tuple]:
    """
    Get words for a specific category and subcategory.
    
    :param category: The category name
    :param subcategory: The subcategory name
    :return: JSON response with words
    """
    try:
        words = get_words_by_category(category, subcategory)
        if not words:
            return jsonify({"error": f"Subcategory '{subcategory}' not found in category '{category}'"}), 404
        
        return jsonify({
            "category": category,
            "subcategory": subcategory,
            "words": words
        })
    except Exception as e:
        logger.error(f"Error getting words for {category}/{subcategory}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/lithuanian/wordlists/_all')
def get_all_words() -> Union[Response, tuple]:
    """
    Get all words from all categories and subcategories.
    
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