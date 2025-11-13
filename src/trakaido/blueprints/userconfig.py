
"""User configuration management for Trakaido Lithuanian language learning."""

# Standard library imports
import json
import os
from typing import Any, Dict, List, Union

# Third-party imports
from flask import Response, g, jsonify, request

# Local application imports
import constants
from atacama.decorators.auth import require_auth
from .shared import trakaido_bp, logger, ensure_user_data_dir

##############################################################################

# API Documentation for corpus choices endpoints
CORPUSCHOICES_API_DOCS = {
    "GET /api/trakaido/corpuschoices/": "Get all corpus choices for authenticated user",
    "PUT /api/trakaido/corpuschoices/": "Save all corpus choices for authenticated user",
    "POST /api/trakaido/corpuschoices/corpus": "Update choices for a specific corpus",
    "GET /api/trakaido/corpuschoices/corpus/{corpus}": "Get choices for a specific corpus"
}

# API Documentation for level progression endpoints
LEVELPROGRESSION_API_DOCS = {
    "GET /api/trakaido/levelprogression": "Get level progression for authenticated user",
    "PUT /api/trakaido/levelprogression": "Update level progression (replaces entire object)",
    "PATCH /api/trakaido/levelprogression/level": "Update just the current level"
}

# Corpus Choices related functions
def get_corpus_choices_file_path(user_id: str, language: str = "lithuanian") -> str:
    """
    Get the file path for a user's corpus choices.

    :param user_id: The user's database ID
    :param language: The language for the corpus choices (default: "lithuanian")
    :return: Path to the user's corpus choices file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language)
    return os.path.join(user_data_dir, "corpuschoices.json")

def load_corpus_choices(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """
    Load corpus choices for a user from their JSON file.

    :param user_id: The user's database ID
    :param language: The language for the corpus choices (default: "lithuanian")
    :return: Dictionary containing the user's corpus choices
    """
    try:
        choices_file = get_corpus_choices_file_path(user_id, language)
        if not os.path.exists(choices_file):
            logger.debug(f"No corpus choices file found for user {user_id}, returning empty choices")
            return {"choices": {}}
        
        with open(choices_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Validate the structure - each corpus should map to a list of group names
        validated_choices = {}
        if "choices" in data and isinstance(data["choices"], dict):
            for corpus, groups in data["choices"].items():
                if isinstance(groups, list) and all(isinstance(group, str) for group in groups):
                    validated_choices[corpus] = groups
                else:
                    logger.warning(f"Invalid groups format for corpus '{corpus}' for user {user_id}, skipping")
        
        return {"choices": validated_choices}
    except Exception as e:
        logger.error(f"Error loading corpus choices for user {user_id}: {str(e)}")
        return {"choices": {}}

def save_corpus_choices(user_id: str, choices: Dict[str, Any], language: str = "lithuanian") -> bool:
    """
    Save corpus choices for a user to their JSON file.

    :param user_id: The user's database ID
    :param choices: Dictionary containing the user's corpus choices
    :param language: The language for the corpus choices (default: "lithuanian")
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id, language)
        choices_file = get_corpus_choices_file_path(user_id, language)
        
        # Validate the structure before saving
        validated_data = {"choices": {}}
        if "choices" in choices and isinstance(choices["choices"], dict):
            for corpus, groups in choices["choices"].items():
                if isinstance(groups, list) and all(isinstance(group, str) for group in groups):
                    validated_data["choices"][corpus] = groups
                else:
                    logger.warning(f"Invalid groups format for corpus '{corpus}', skipping")
        
        with open(choices_file, 'w', encoding='utf-8') as f:
            json.dump(validated_data, f, ensure_ascii=False)
        
        logger.debug(f"Successfully saved corpus choices for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving corpus choices for user {user_id}: {str(e)}")
        return False

def validate_corpus_exists(corpus: str) -> bool:
    """
    Validate that a corpus exists in the available wordlist corpora.

    Deprecated - always returns true
    """
    return True

def validate_groups_in_corpus(corpus: str, groups: List[str]) -> List[str]:
    """
    Validate that groups exist in the specified corpus and return only valid ones.

    Deprecated - returns all groups
    """
    return groups


# Level Progression related functions
def get_level_progression_file_path(user_id: str, language: str = "lithuanian") -> str:
    """
    Get the file path for a user's level progression data.

    :param user_id: The user's database ID
    :param language: The language for the level progression (default: "lithuanian")
    :return: Path to the user's level progression file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language)
    return os.path.join(user_data_dir, "levelprogression.json")


def migrate_corpus_choices_to_level_progression(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """
    Migrate old corpuschoices.json data to levelprogression.json format.

    Converts corpus choices like:
      {"choices": {"level_1": ["group1", "group2"], "level_3": ["group3"]}}

    To level progression format:
      {"currentLevel": 3, "levelOverrides": {"level_1": ["group1", "group2"], "level_3": ["group3"]}}

    :param user_id: The user's database ID
    :param language: The language for the corpus choices (default: "lithuanian")
    :return: Dictionary with migrated level progression data
    """
    try:
        corpus_choices = load_corpus_choices(user_id, language)
        choices = corpus_choices.get("choices", {})

        if not choices:
            return {"currentLevel": 1}

        # Find the highest level number
        max_level = 1
        level_overrides = {}

        for corpus_key, groups in choices.items():
            # Extract level number from keys like "level_1", "level_2", etc.
            if corpus_key.startswith("level_"):
                try:
                    level_num = int(corpus_key.split("_")[1])
                    max_level = max(max_level, level_num)
                    # Store as override if groups is a list
                    if isinstance(groups, list) and groups:
                        level_overrides[corpus_key] = groups
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse level number from corpus key: {corpus_key}")

        result = {"currentLevel": max_level}
        if level_overrides:
            result["levelOverrides"] = level_overrides

        logger.info(f"Migrated corpus choices to level progression for user {user_id}: currentLevel={max_level}")
        return result

    except Exception as e:
        logger.error(f"Error migrating corpus choices for user {user_id}: {str(e)}")
        return {"currentLevel": 1}


def load_level_progression(user_id: str, auto_migrate: bool = True, language: str = "lithuanian") -> Dict[str, Any]:
    """
    Load level progression for a user from their JSON file.

    :param user_id: The user's database ID
    :param auto_migrate: If True, automatically migrate from corpus choices if needed
    :param language: The language for the level progression (default: "lithuanian")
    :return: Dictionary containing the user's level progression
    """
    try:
        progression_file = get_level_progression_file_path(user_id, language)

        # If file exists, load it
        if os.path.exists(progression_file):
            with open(progression_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate structure
            if "currentLevel" in data and isinstance(data["currentLevel"], int):
                result = {"currentLevel": data["currentLevel"]}

                # Validate levelOverrides if present
                if "levelOverrides" in data and isinstance(data["levelOverrides"], dict):
                    validated_overrides = {}
                    for level_key, groups in data["levelOverrides"].items():
                        if groups is None:
                            validated_overrides[level_key] = None
                        elif isinstance(groups, list):
                            validated_overrides[level_key] = groups
                        else:
                            logger.warning(f"Invalid override format for {level_key}, skipping")

                    if validated_overrides:
                        result["levelOverrides"] = validated_overrides

                return result
            else:
                logger.warning(f"Invalid level progression structure for user {user_id}")

        # No progression file found, try migration if enabled
        if auto_migrate:
            migrated_data = migrate_corpus_choices_to_level_progression(user_id, language)
            # Save the migrated data
            if save_level_progression(user_id, migrated_data, language):
                logger.info(f"Successfully migrated and saved level progression for user {user_id} language {language}")
            return migrated_data

        # Default: level 1
        return {"currentLevel": 1}

    except Exception as e:
        logger.error(f"Error loading level progression for user {user_id}: {str(e)}")
        return {"currentLevel": 1}


def save_level_progression(user_id: str, progression: Dict[str, Any], language: str = "lithuanian") -> bool:
    """
    Save level progression for a user to their JSON file.

    :param user_id: The user's database ID
    :param progression: Dictionary containing the user's level progression
    :param language: The language for the level progression (default: "lithuanian")
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id, language)
        progression_file = get_level_progression_file_path(user_id, language)

        # Validate structure
        if "currentLevel" not in progression or not isinstance(progression["currentLevel"], int):
            logger.error(f"Invalid progression data for user {user_id}: missing or invalid currentLevel")
            return False

        validated_data = {"currentLevel": progression["currentLevel"]}

        # Validate levelOverrides if present
        if "levelOverrides" in progression and isinstance(progression["levelOverrides"], dict):
            validated_overrides = {}
            for level_key, groups in progression["levelOverrides"].items():
                if groups is None:
                    validated_overrides[level_key] = None
                elif isinstance(groups, list):
                    validated_overrides[level_key] = groups
                else:
                    logger.warning(f"Invalid override format for {level_key}, skipping")

            if validated_overrides:
                validated_data["levelOverrides"] = validated_overrides

        with open(progression_file, 'w', encoding='utf-8') as f:
            json.dump(validated_data, f, ensure_ascii=False)

        logger.debug(f"Successfully saved level progression for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving level progression for user {user_id}: {str(e)}")
        return False


# Corpus Choices API Routes
@trakaido_bp.route('/api/trakaido/corpuschoices/', methods=['GET'])
@require_auth
def get_all_corpus_choices() -> Union[Response, tuple]:
    """
    Get all corpus choices for the authenticated user.

    :return: JSON response with all corpus choices
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        choices = load_corpus_choices(user_id, language)
        return jsonify(choices)
    except Exception as e:
        logger.error(f"Error getting all corpus choices: {str(e)}")
        return jsonify({"error": str(e)}), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/', methods=['PUT'])
@require_auth
def save_all_corpus_choices() -> Union[Response, tuple]:
    """
    Save all corpus choices for the authenticated user, replacing any existing choices.

    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "choices" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'choices' field.",
                "code": "INVALID_REQUEST"
            }), 400

        # Validate each corpus and its groups
        validated_choices = {"choices": {}}
        for corpus, groups in data["choices"].items():
            if not isinstance(groups, list):
                logger.warning(f"Invalid groups format for corpus '{corpus}', skipping")
                continue

            if validate_corpus_exists(corpus):
                valid_groups = validate_groups_in_corpus(corpus, groups)
                if valid_groups:  # Only store if there are valid groups
                    validated_choices["choices"][corpus] = valid_groups
            else:
                logger.warning(f"Corpus '{corpus}' does not exist, skipping")

        success = save_corpus_choices(user_id, validated_choices, language)
        if success:
            return jsonify({
                "success": True,
                "message": "Corpus choices saved successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save corpus choices",
                "code": "STORAGE_ERROR"
            }), 500
    except Exception as e:
        logger.error(f"Error saving all corpus choices: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/corpus', methods=['POST'])
@require_auth
def update_corpus_choices() -> Union[Response, tuple]:
    """
    Update the selected groups for a specific corpus.

    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "corpus" not in data or "groups" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'corpus' and 'groups' fields.",
                "code": "INVALID_REQUEST"
            }), 400

        corpus = data["corpus"]
        groups = data["groups"]

        if not isinstance(groups, list):
            return jsonify({
                "success": False,
                "error": "Groups must be an array of strings",
                "code": "INVALID_REQUEST"
            }), 400

        # Validate corpus exists
        if not validate_corpus_exists(corpus):
            return jsonify({
                "success": False,
                "error": f"Corpus '{corpus}' not found",
                "code": "CORPUS_NOT_FOUND"
            }), 400

        # Validate groups exist in corpus
        valid_groups = validate_groups_in_corpus(corpus, groups)

        # Load existing choices
        all_choices = load_corpus_choices(user_id, language)

        # Update the specific corpus choices
        if valid_groups:
            all_choices["choices"][corpus] = valid_groups
        elif corpus in all_choices["choices"]:
            # Remove corpus if no valid groups remain
            del all_choices["choices"][corpus]

        # Save back to file
        success = save_corpus_choices(user_id, all_choices, language)
        if success:
            return jsonify({
                "success": True,
                "message": "Corpus choices updated successfully",
                "corpus": corpus,
                "groups": valid_groups
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to update corpus choices",
                "code": "STORAGE_ERROR"
            }), 500
    except Exception as e:
        logger.error(f"Error updating corpus choices: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500

@trakaido_bp.route('/api/trakaido/corpuschoices/corpus/<corpus>', methods=['GET'])
@require_auth
def get_corpus_choices(corpus: str) -> Union[Response, tuple]:
    """
    Get the selected groups for a specific corpus.

    :param corpus: The name of the corpus
    :return: JSON response with corpus choices
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        all_choices = load_corpus_choices(user_id, language)

        # Get groups for the specific corpus, or empty array if not found
        groups = all_choices["choices"].get(corpus, [])

        return jsonify({
            "corpus": corpus,
            "groups": groups
        })
    except Exception as e:
        logger.error(f"Error getting corpus choices for '{corpus}': {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500


# Level Progression API Routes
@trakaido_bp.route('/api/trakaido/levelprogression', methods=['GET'])
@require_auth
def get_level_progression() -> Union[Response, tuple]:
    """
    Get level progression for the authenticated user.

    Returns the user's current level and optional level overrides.
    Automatically migrates from old corpus choices format if needed.

    :return: JSON response with level progression data
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        progression = load_level_progression(user_id, auto_migrate=True, language=language)
        return jsonify(progression)
    except Exception as e:
        logger.error(f"Error getting level progression: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/levelprogression', methods=['PUT'])
@require_auth
def update_level_progression() -> Union[Response, tuple]:
    """
    Update level progression for the authenticated user.

    Replaces the entire progression object. Request body should contain:
    {
        "currentLevel": 10,
        "levelOverrides": {  // optional
            "level_5": ["group1", "group2"]
        }
    }

    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "currentLevel" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'currentLevel' field.",
                "code": "INVALID_REQUEST"
            }), 400

        current_level = data["currentLevel"]

        # Validate currentLevel
        if not isinstance(current_level, int) or current_level < 1:
            return jsonify({
                "success": False,
                "error": "'currentLevel' must be a positive integer",
                "code": "INVALID_REQUEST"
            }), 400

        # Build progression object
        progression = {"currentLevel": current_level}

        # Handle optional levelOverrides
        if "levelOverrides" in data:
            level_overrides = data["levelOverrides"]

            if level_overrides is not None:
                if not isinstance(level_overrides, dict):
                    return jsonify({
                        "success": False,
                        "error": "'levelOverrides' must be an object or null",
                        "code": "INVALID_REQUEST"
                    }), 400

                # Validate each override
                validated_overrides = {}
                for level_key, groups in level_overrides.items():
                    if groups is None:
                        validated_overrides[level_key] = None
                    elif isinstance(groups, list):
                        # Validate all items are strings
                        if all(isinstance(g, str) for g in groups):
                            validated_overrides[level_key] = groups
                        else:
                            return jsonify({
                                "success": False,
                                "error": f"All groups in '{level_key}' must be strings",
                                "code": "INVALID_REQUEST"
                            }), 400
                    else:
                        return jsonify({
                            "success": False,
                            "error": f"Override for '{level_key}' must be an array or null",
                            "code": "INVALID_REQUEST"
                        }), 400

                if validated_overrides:
                    progression["levelOverrides"] = validated_overrides

        # Save progression
        success = save_level_progression(user_id, progression, language)
        if success:
            return jsonify({
                "success": True,
                **progression
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save level progression",
                "code": "STORAGE_ERROR"
            }), 500

    except Exception as e:
        logger.error(f"Error updating level progression: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500


@trakaido_bp.route('/api/trakaido/levelprogression/level', methods=['PATCH'])
@require_auth
def update_current_level() -> Union[Response, tuple]:
    """
    Update just the current level without modifying overrides.

    Request body should contain:
    {
        "currentLevel": 15
    }

    :return: JSON response indicating success or error
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "currentLevel" not in data:
            return jsonify({
                "success": False,
                "error": "Invalid request body. Expected 'currentLevel' field.",
                "code": "INVALID_REQUEST"
            }), 400

        current_level = data["currentLevel"]

        # Validate currentLevel
        if not isinstance(current_level, int) or current_level < 1:
            return jsonify({
                "success": False,
                "error": "'currentLevel' must be a positive integer",
                "code": "INVALID_REQUEST"
            }), 400

        # Load existing progression
        existing_progression = load_level_progression(user_id, auto_migrate=True, language=language)

        # Update only the currentLevel
        existing_progression["currentLevel"] = current_level

        # Save back
        success = save_level_progression(user_id, existing_progression, language)
        if success:
            return jsonify({
                "success": True,
                **existing_progression
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save level progression",
                "code": "STORAGE_ERROR"
            }), 500

    except Exception as e:
        logger.error(f"Error updating current level: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STORAGE_ERROR"
        }), 500
