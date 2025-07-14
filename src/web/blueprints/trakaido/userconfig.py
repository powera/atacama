
"""User configuration management for Trakaido Lithuanian language learning."""

# Standard library imports
import json
import os
from typing import Any, Dict, List, Union

# Third-party imports
from flask import Response, g, jsonify, request

# Local application imports
import constants
from web.decorators import require_auth
from .shared import trakaido_bp, logger, ensure_user_data_dir, get_wordlist_corpora, get_groups

# Corpus Choices related functions
def get_corpus_choices_file_path(user_id: str) -> str:
    """
    Get the file path for a user's corpus choices.
    
    :param user_id: The user's database ID
    :return: Path to the user's corpus choices file
    """
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id))
    return os.path.join(user_data_dir, "corpuschoices.json")

def load_corpus_choices(user_id: str) -> Dict[str, Any]:
    """
    Load corpus choices for a user from their JSON file.
    
    :param user_id: The user's database ID
    :return: Dictionary containing the user's corpus choices
    """
    try:
        choices_file = get_corpus_choices_file_path(user_id)
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

def save_corpus_choices(user_id: str, choices: Dict[str, Any]) -> bool:
    """
    Save corpus choices for a user to their JSON file.
    
    :param user_id: The user's database ID
    :param choices: Dictionary containing the user's corpus choices
    :return: True if successful, False otherwise
    """
    try:
        ensure_user_data_dir(user_id)
        choices_file = get_corpus_choices_file_path(user_id)
        
        # Validate the structure before saving
        validated_data = {"choices": {}}
        if "choices" in choices and isinstance(choices["choices"], dict):
            for corpus, groups in choices["choices"].items():
                if isinstance(groups, list) and all(isinstance(group, str) for group in groups):
                    validated_data["choices"][corpus] = groups
                else:
                    logger.warning(f"Invalid groups format for corpus '{corpus}', skipping")
        
        with open(choices_file, 'w', encoding='utf-8') as f:
            json.dump(validated_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Successfully saved corpus choices for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving corpus choices for user {user_id}: {str(e)}")
        return False

def validate_corpus_exists(corpus: str) -> bool:
    """
    Validate that a corpus exists in the available wordlist corpora.
    
    :param corpus: The corpus name to validate
    :return: True if corpus exists, False otherwise
    """
    try:
        available_corpora = get_wordlist_corpora()
        return corpus in available_corpora
    except Exception as e:
        logger.error(f"Error validating corpus '{corpus}': {str(e)}")
        return False

def validate_groups_in_corpus(corpus: str, groups: List[str]) -> List[str]:
    """
    Validate that groups exist in the specified corpus and return only valid ones.
    
    :param corpus: The corpus name
    :param groups: List of group names to validate
    :return: List of valid group names
    """
    try:
        if not validate_corpus_exists(corpus):
            logger.warning(f"Corpus '{corpus}' does not exist")
            return []
        
        available_groups = get_groups(corpus)
        valid_groups = [group for group in groups if group in available_groups]
        
        invalid_groups = [group for group in groups if group not in available_groups]
        if invalid_groups:
            logger.warning(f"Invalid groups for corpus '{corpus}': {invalid_groups}")
        
        return valid_groups
    except Exception as e:
        logger.error(f"Error validating groups for corpus '{corpus}': {str(e)}")
        return []


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
        choices = load_corpus_choices(user_id)
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
        
        success = save_corpus_choices(user_id, validated_choices)
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
        all_choices = load_corpus_choices(user_id)
        
        # Update the specific corpus choices
        if valid_groups:
            all_choices["choices"][corpus] = valid_groups
        elif corpus in all_choices["choices"]:
            # Remove corpus if no valid groups remain
            del all_choices["choices"][corpus]
        
        # Save back to file
        success = save_corpus_choices(user_id, all_choices)
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
        all_choices = load_corpus_choices(user_id)
        
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
