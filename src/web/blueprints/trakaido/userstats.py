
"""Journey stats management for Lithuanian language learning."""

# Standard library imports
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union

# Third-party imports
from flask import Response, abort, g, jsonify, request, send_file

# Local application imports
import constants
from web.decorators import optional_auth, require_auth
from .shared import *

##############################################################################

# API Documentation for journey stats endpoints
USERSTATS_API_DOCS = {
    "GET /api/trakaido/journeystats/": "Get all journey stats for authenticated user",
    "PUT /api/trakaido/journeystats/": "Save all journey stats for authenticated user",
    "POST /api/trakaido/journeystats/word": "Update stats for a specific word",
    "GET /api/trakaido/journeystats/word/{wordKey}": "Get stats for a specific word",
    "POST /api/trakaido/journeystats/increment": "Increment stats for a single question with nonce",
    "GET /api/trakaido/journeystats/daily": "Get daily stats (today's progress)"
}

# Journey Stats related functions
VALID_STAT_TYPES = {"multipleChoice", "listeningEasy", "listeningHard", "typing"}

# Daily stats constants
DAILY_CUTOFF_HOUR = 7  # 0700 GMT
DAILY_CUTOFF_TIMEZONE = timezone.utc

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
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen", "lastCorrectAnswer"]:
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
                    if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen", "lastCorrectAnswer"]:
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


def save_journey_stats_with_daily_update(user_id: str, stats: Dict[str, Any]) -> bool:
    """
    Save journey stats and update daily snapshots.
    
    :param user_id: The user's database ID
    :param stats: Dictionary containing the user's journey stats
    :return: True if successful, False otherwise
    """
    try:
        if not ensure_daily_snapshots(user_id):
            logger.warning(f"Failed to ensure daily snapshots for user {user_id}")
        
        # Save the overall stats after ensuring snapshots
        if not save_journey_stats(user_id, stats):
            return False
        
        # Update current daily snapshot
        current_day = get_current_day_key()
        if not save_daily_stats_snapshot(user_id, current_day, "current", stats):
            logger.warning(f"Failed to update current daily snapshot for user {user_id}")
            # Don't fail the whole operation, just log the warning
        
        return True
    except Exception as e:
        logger.error(f"Error saving journey stats with daily update for user {user_id}: {str(e)}")
        return False

def filter_word_stats(word_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter word stats to include only valid stat types.
    
    :param word_stats: Raw word stats dictionary
    :return: Filtered word stats dictionary
    """
    filtered_stats = {}
    for stat_type, stat_data in word_stats.items():
        if stat_type in VALID_STAT_TYPES or stat_type in ["exposed", "lastSeen", "lastCorrectAnswer"]:
            filtered_stats[stat_type] = stat_data
        else:
            logger.debug(f"Filtering out invalid stat type '{stat_type}'")
    return filtered_stats


# Daily Stats Functions
def get_current_day_key() -> str:
    """
    Get the current day key based on 0700 GMT cutoff.
    
    :return: Day key in format YYYY-MM-DD
    """
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    # If it's before 7 AM, consider it the previous day
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def get_daily_stats_dir(user_id: str) -> str:
    """
    Get the directory path for a user's daily stats.
    
    :param user_id: The user's database ID
    :return: Path to the user's daily stats directory
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), "daily")
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def get_daily_stats_file_path(user_id: str, day_key: str, stats_type: str) -> str:
    """
    Get the file path for a user's daily stats file.
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :param stats_type: Either 'current' or 'yesterday'
    :return: Path to the daily stats file
    """
    daily_dir = get_daily_stats_dir(user_id)
    return os.path.join(daily_dir, f"{day_key}_{stats_type}.json")


def get_nonce_file_path(user_id: str, day_key: str) -> str:
    """
    Get the file path for a user's nonce tracking file.
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :return: Path to the nonce file
    """
    daily_dir = get_daily_stats_dir(user_id)
    return os.path.join(daily_dir, f"{day_key}_nonces.json")


def load_daily_stats_snapshot(user_id: str, day_key: str, stats_type: str) -> Dict[str, Any]:
    """
    Load a daily stats snapshot (current or yesterday).
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :param stats_type: Either 'current' or 'yesterday'
    :return: Dictionary containing the daily stats snapshot
    """
    try:
        stats_file = get_daily_stats_file_path(user_id, day_key, stats_type)
        if not os.path.exists(stats_file):
            logger.debug(f"No {stats_type} stats file found for user {user_id} day {day_key}, returning empty stats")
            return {"stats": {}}
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data if isinstance(data, dict) and "stats" in data else {"stats": {}}
    except Exception as e:
        logger.error(f"Error loading {stats_type} daily stats for user {user_id} day {day_key}: {str(e)}")
        return {"stats": {}}


def save_daily_stats_snapshot(user_id: str, day_key: str, stats_type: str, stats: Dict[str, Any]) -> bool:
    """
    Save a daily stats snapshot (current or yesterday).
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :param stats_type: Either 'current' or 'yesterday'
    :param stats: Dictionary containing the daily stats snapshot
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        stats_file = get_daily_stats_file_path(user_id, day_key, stats_type)
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully saved {stats_type} daily stats for user {user_id} day {day_key}")
        return True
    except Exception as e:
        logger.error(f"Error saving {stats_type} daily stats for user {user_id} day {day_key}: {str(e)}")
        return False


def load_nonces(user_id: str, day_key: str) -> set:
    """
    Load used nonces for a specific day.
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :return: Set of used nonces
    """
    try:
        nonce_file = get_nonce_file_path(user_id, day_key)
        if not os.path.exists(nonce_file):
            return set()
        
        with open(nonce_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return set(data.get("nonces", []))
    except Exception as e:
        logger.error(f"Error loading nonces for user {user_id} day {day_key}: {str(e)}")
        return set()


def save_nonces(user_id: str, day_key: str, nonces: set) -> bool:
    """
    Save used nonces for a specific day.
    
    :param user_id: The user's database ID
    :param day_key: Day key in format YYYY-MM-DD
    :param nonces: Set of used nonces
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        nonce_file = get_nonce_file_path(user_id, day_key)
        
        with open(nonce_file, 'w', encoding='utf-8') as f:
            json.dump({"nonces": list(nonces)}, f, indent=2)
        
        logger.debug(f"Successfully saved nonces for user {user_id} day {day_key}")
        return True
    except Exception as e:
        logger.error(f"Error saving nonces for user {user_id} day {day_key}: {str(e)}")
        return False


def ensure_daily_snapshots(user_id: str) -> bool:
    """
    Ensure that daily snapshots are properly set up for the current day.
    This should be called before any daily stats operations.
    
    :param user_id: The user's database ID
    :return: True if successful, False otherwise
    """
    try:
        current_day = get_current_day_key()
        
        # Check if we need to create yesterday's snapshot
        yesterday_stats = load_daily_stats_snapshot(user_id, current_day, "yesterday")
        if not yesterday_stats["stats"]:
            # Load current overall stats as yesterday's baseline
            overall_stats = load_journey_stats(user_id)
            save_daily_stats_snapshot(user_id, current_day, "yesterday", overall_stats)
            logger.debug(f"Created yesterday snapshot for user {user_id} day {current_day}")
        
        # Ensure current snapshot exists (can be empty)
        current_stats = load_daily_stats_snapshot(user_id, current_day, "current")
        if not os.path.exists(get_daily_stats_file_path(user_id, current_day, "current")):
            # Initialize with current overall stats
            overall_stats = load_journey_stats(user_id)
            save_daily_stats_snapshot(user_id, current_day, "current", overall_stats)
            logger.debug(f"Created current snapshot for user {user_id} day {current_day}")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring daily snapshots for user {user_id}: {str(e)}")
        return False


def calculate_daily_progress(user_id: str) -> Dict[str, Any]:
    """
    Calculate daily progress by comparing current and yesterday snapshots.
    
    :param user_id: The user's database ID
    :return: Dictionary containing daily progress stats
    """
    try:
        current_day = get_current_day_key()
        
        # Ensure snapshots exist
        if not ensure_daily_snapshots(user_id):
            return {"error": "Failed to ensure daily snapshots"}
        
        yesterday_stats = load_daily_stats_snapshot(user_id, current_day, "yesterday")
        current_stats = load_daily_stats_snapshot(user_id, current_day, "current")
        
        daily_progress = {}
        
        # Calculate progress for each stat type
        for stat_type in VALID_STAT_TYPES:
            daily_progress[stat_type] = {"correct": 0, "incorrect": 0}
        
        # Go through all words in current stats
        for word_key, current_word_stats in current_stats["stats"].items():
            yesterday_word_stats = yesterday_stats["stats"].get(word_key, {})
            
            for stat_type in VALID_STAT_TYPES:
                if stat_type in current_word_stats and isinstance(current_word_stats[stat_type], dict):
                    current_correct = current_word_stats[stat_type].get("correct", 0)
                    current_incorrect = current_word_stats[stat_type].get("incorrect", 0)
                    
                    yesterday_correct = 0
                    yesterday_incorrect = 0
                    if stat_type in yesterday_word_stats and isinstance(yesterday_word_stats[stat_type], dict):
                        yesterday_correct = yesterday_word_stats[stat_type].get("correct", 0)
                        yesterday_incorrect = yesterday_word_stats[stat_type].get("incorrect", 0)
                    
                    # Calculate delta
                    daily_progress[stat_type]["correct"] += max(0, current_correct - yesterday_correct)
                    daily_progress[stat_type]["incorrect"] += max(0, current_incorrect - yesterday_incorrect)
        
        return {
            "day": current_day,
            "progress": daily_progress
        }
    except Exception as e:
        logger.error(f"Error calculating daily progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


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
        
        success = save_journey_stats_with_daily_update(user_id, data)
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
        
        # Save back to file with daily update
        success = save_journey_stats_with_daily_update(user_id, all_stats)
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


@trakaido_bp.route('/api/trakaido/journeystats/increment', methods=['POST'])
@require_auth
def increment_word_stats() -> Union[Response, tuple]:
    """
    Increment stats for a single question with nonce protection.
    
    Expected request body:
    {
        "wordKey": "word-translation",
        "statType": "multipleChoice",
        "correct": true,
        "nonce": "unique-identifier"
    }
    
    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()
        
        # Validate request body
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
        
        required_fields = ["wordKey", "statType", "correct", "nonce"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        word_key = data["wordKey"]
        stat_type = data["statType"]
        correct = data["correct"]
        nonce = data["nonce"]
        
        # Validate stat type
        if stat_type not in VALID_STAT_TYPES:
            return jsonify({"error": f"Invalid stat type: {stat_type}. Valid types: {list(VALID_STAT_TYPES)}"}), 400
        
        # Validate correct field
        if not isinstance(correct, bool):
            return jsonify({"error": "Field 'correct' must be a boolean"}), 400
        
        # Validate nonce
        if not isinstance(nonce, str) or not nonce.strip():
            return jsonify({"error": "Field 'nonce' must be a non-empty string"}), 400
        
        current_day = get_current_day_key()
        
        # Check if nonce has already been used
        used_nonces = load_nonces(user_id, current_day)
        if nonce in used_nonces:
            logger.warning(f"Duplicate nonce '{nonce}' for user {user_id} on day {current_day}")
            return jsonify({"error": "Nonce already used"}), 409
        
        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id):
            return jsonify({"error": "Failed to initialize daily stats"}), 500
        
        # Load current overall stats
        all_stats = load_journey_stats(user_id)
        
        # Initialize word stats if they don't exist
        if word_key not in all_stats["stats"]:
            all_stats["stats"][word_key] = {}
        
        if stat_type not in all_stats["stats"][word_key]:
            all_stats["stats"][word_key][stat_type] = {"correct": 0, "incorrect": 0}
        
        # Increment the appropriate counter
        if correct:
            all_stats["stats"][word_key][stat_type]["correct"] += 1
        else:
            all_stats["stats"][word_key][stat_type]["incorrect"] += 1
        
        # Update lastSeen timestamp
        current_timestamp = int(datetime.now().timestamp() * 1000)
        all_stats["stats"][word_key]["lastSeen"] = current_timestamp
        
        # Update lastCorrectAnswer timestamp if the answer was correct
        if correct:
            all_stats["stats"][word_key]["lastCorrectAnswer"] = current_timestamp
        
        # Mark word as exposed
        all_stats["stats"][word_key]["exposed"] = True
        
        # Save updated overall stats and update daily snapshots
        if not save_journey_stats_with_daily_update(user_id, all_stats):
            return jsonify({"error": "Failed to save stats"}), 500
        
        # Add nonce to used nonces
        used_nonces.add(nonce)
        if not save_nonces(user_id, current_day, used_nonces):
            logger.warning(f"Failed to save nonce for user {user_id} day {current_day}")
        
        logger.debug(f"Successfully incremented {stat_type} stats for word '{word_key}' (correct: {correct}) for user {user_id}")
        
        return jsonify({
            "success": True,
            "wordKey": word_key,
            "statType": stat_type,
            "correct": correct,
            "newStats": all_stats["stats"][word_key][stat_type]
        })
        
    except Exception as e:
        logger.error(f"Error incrementing word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/daily', methods=['GET'])
@require_auth
def get_daily_stats() -> Union[Response, tuple]:
    """
    Get daily stats (today's progress) for the authenticated user.
    
    :return: JSON response with daily progress stats
    """
    try:
        user_id = str(g.user.id)
        daily_progress = calculate_daily_progress(user_id)
        
        if "error" in daily_progress:
            return jsonify(daily_progress), 500
        
        return jsonify(daily_progress)
    except Exception as e:
        logger.error(f"Error getting daily stats: {str(e)}")
        return jsonify({"error": str(e)}), 500