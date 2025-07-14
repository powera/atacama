
"""Journey stats management for Lithuanian language learning."""

# Standard library imports
import json
import os
from typing import Any, Dict, List, Optional, Union

# Third-party imports
from flask import Response, abort, g, jsonify, request, send_file

# Local application imports
import constants
from web.decorators import optional_auth, require_auth
from .shared import *

# Journey Stats related functions
VALID_STAT_TYPES = {"multipleChoice", "listeningEasy", "listeningHard", "typing"}

def get_journey_stats_file_path(user_id: str) -> str:
    """
    Get the file path for a user's journey stats.
    
    :param user_id: The user's database ID
    :return: Path to the user's Lithuanian journey stats file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    return os.path.join(user_data_dir, "lithuanian.json")


def load_journey_stats(user_id: str) -> Dict[str, Any]:
    """
    Load journey stats for a user from their JSON file.
    
    :param user_id: The user's database ID
    :return: Dictionary containing the user's journey stats
    """
    try:
        stats_file = get_journey_stats_file_path(user_id)
        if not os.path.exists(stats_file):
            logger.debug(f"DEBUG: No stats file found for user {user_id}, returning empty stats")
            return {"stats": {}}
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Filter out invalid stat types
        filtered_stats = {}
        if "stats" in data:
            for word_key, word_stats in data["stats"].items():
                filtered_word_stats = {}
                for stat_type, stat_data in word_stats.items():
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
                        filtered_word_stats[stat_type] = stat_data
                    else:
                        logger.debug(f"Filtering out invalid stat type '{stat_type}' for word '{word_key}'")
                filtered_stats[word_key] = filtered_word_stats
        
        return {"stats": filtered_stats}
    except Exception as e:
        logger.error(f"Error loading journey stats for user {user_id}: {str(e)}")
        return {"stats": {}}

def save_journey_stats(user_id: str, stats: Dict[str, Any]) -> bool:
    """
    Save journey stats for a user to their JSON file.
    
    :param user_id: The user's database ID
    :param stats: Dictionary containing the user's journey stats
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        stats_file = get_journey_stats_file_path(user_id)
        
        # Filter out invalid stat types before saving
        filtered_data = {"stats": {}}
        if "stats" in stats:
            for word_key, word_stats in stats["stats"].items():
                filtered_word_stats = {}
                for stat_type, stat_data in word_stats.items():
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
                        filtered_word_stats[stat_type] = stat_data
                    else:
                        logger.debug(f"Filtering out invalid stat type '{stat_type}' for word '{word_key}' before saving")
                filtered_data["stats"][word_key] = filtered_word_stats
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully saved journey stats for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving journey stats for user {user_id}: {str(e)}")
        return False

def filter_word_stats(word_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter word stats to include only valid stat types.
    
    :param word_stats: Raw word stats dictionary
    :return: Filtered word stats dictionary
    """
    filtered_stats = {}
    for stat_type, stat_data in word_stats.items():
        if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen"]:
            filtered_stats[stat_type] = stat_data
        else:
            logger.debug(f"Filtering out invalid stat type '{stat_type}'")
    return filtered_stats


# Journey Stats API Routes
@trakaido_bp.route('/api/trakaido/journeystats/', methods=['GET'])
@require_auth
def get_all_journey_stats() -> Union[Response, tuple]:
    """
    Get all journey stats for the authenticated user.
    
    :return: JSON response with all journey stats
    """
    try:
        user_id = str(g.user.id)
        stats = load_journey_stats(user_id)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/', methods=['PUT'])
@require_auth
def save_all_journey_stats() -> Union[Response, tuple]:
    """
    Save all journey stats for the authenticated user.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "stats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'stats' field."}), 400
        
        success = save_journey_stats(user_id, data)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to save journey stats"}), 500
    except Exception as e:
        logger.error(f"Error saving all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/word', methods=['POST'])
@require_auth
def update_word_stats() -> Union[Response, tuple]:
    """
    Update stats for a specific word for the authenticated user.
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        if not data or "wordKey" not in data or "wordStats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'wordKey' and 'wordStats' fields."}), 400
        
        word_key = data["wordKey"]
        word_stats = data["wordStats"]
        
        # Filter the word stats to include only valid types
        filtered_word_stats = filter_word_stats(word_stats)
        
        # Load existing stats
        all_stats = load_journey_stats(user_id)
        
        # Update the specific word stats
        all_stats["stats"][word_key] = filtered_word_stats
        
        # Save back to file
        success = save_journey_stats(user_id, all_stats)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update word stats"}), 500
    except Exception as e:
        logger.error(f"Error updating word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/journeystats/word/<word_key>', methods=['GET'])
@require_auth
def get_word_stats(word_key: str) -> Union[Response, tuple]:
    """
    Get stats for a specific word for the authenticated user.
    
    :param word_key: The word key to get stats for
    :return: JSON response with word stats
    """
    try:
        user_id = str(g.user.id)
        all_stats = load_journey_stats(user_id)
        
        word_stats = all_stats["stats"].get(word_key, {})
        
        return jsonify({"wordStats": word_stats})
    except Exception as e:
        logger.error(f"Error getting word stats for '{word_key}': {str(e)}")
        return jsonify({"error": str(e)}), 500