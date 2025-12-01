"""User configuration API (Version 2) for Trakaido.

This API manages user preferences and settings across all Trakaido platforms.
Consolidates learning preferences, display settings, and audio configuration
into a unified configuration system stored in flat files.
"""

# Standard library imports
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports
from flask import g, jsonify, request

# Local application imports
import constants
from atacama.decorators.auth import require_auth
from common.base.logging_config import get_logger
from trakaido.blueprints.shared import trakaido_bp, ensure_user_data_dir

logger = get_logger(__name__)

##############################################################################
# Configuration Schema and Defaults
##############################################################################

# Valid enum values for configuration fields
VALID_PROFICIENCY_LEVELS = ["beginner", "intermediate", "advanced"]
VALID_COLOR_SCHEMES = ["system", "light", "dark"]

# Default configuration structure
DEFAULT_CONFIG = {
    "learning": {
        "currentLevel": 1,
        "userProficiency": "beginner",
        "journeyAutoAdvance": True,
        "showMotivationalBreaks": True
    },
    "audio": {
        "enabled": True,
        "selectedVoice": "random",
        "downloadOnWiFiOnly": True
    },
    "display": {
        "colorScheme": "system",
        "showGrammarInterstitials": True
    },
    "metadata": {
        "hasCompletedOnboarding": False,
        "lastModified": None
    }
}

##############################################################################
# File I/O Functions
##############################################################################

def get_userconfig_file_path(user_id: str, language: str = "lithuanian") -> str:
    """Get the file path for a user's configuration file."""
    user_dir = ensure_user_data_dir(user_id, language)
    return os.path.join(user_dir, "userconfig.json")


def load_user_config(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Load user configuration from file, returns default config if not found."""
    try:
        config_file = get_userconfig_file_path(user_id, language)

        if not os.path.exists(config_file):
            logger.info(f"No config file found for user {user_id} language {language}, returning defaults")
            return _deep_copy_config(DEFAULT_CONFIG)

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Merge with defaults to ensure all fields exist
        return _merge_with_defaults(config)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file for user {user_id} language {language}: {str(e)}")
        return _deep_copy_config(DEFAULT_CONFIG)
    except Exception as e:
        logger.error(f"Error loading config for user {user_id} language {language}: {str(e)}")
        return _deep_copy_config(DEFAULT_CONFIG)


def save_user_config(user_id: str, config: Dict[str, Any], language: str = "lithuanian") -> bool:
    """Save user configuration to file."""
    try:
        config_file = get_userconfig_file_path(user_id, language)

        # Update lastModified timestamp
        if "metadata" not in config:
            config["metadata"] = {}
        config["metadata"]["lastModified"] = datetime.utcnow().isoformat() + "Z"

        # Ensure directory exists
        ensure_user_data_dir(user_id, language)

        # Write to file with atomic operation
        temp_file = config_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Atomic rename
        os.replace(temp_file, config_file)

        logger.info(f"Saved config for user {user_id} language {language}")
        return True

    except Exception as e:
        logger.error(f"Error saving config for user {user_id} language {language}: {str(e)}")
        return False


def _deep_copy_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Deep copy configuration dictionary."""
    return json.loads(json.dumps(config))


def _merge_with_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge user config with defaults to ensure all fields exist."""
    merged = _deep_copy_config(DEFAULT_CONFIG)

    # Merge each top-level section
    for section in ["learning", "audio", "display", "metadata"]:
        if section in config and isinstance(config[section], dict):
            if section in merged:
                merged[section].update(config[section])
            else:
                merged[section] = config[section]

    return merged


##############################################################################
# Validation Functions
##############################################################################

def validate_config_update(updates: Dict[str, Any]) -> tuple[bool, Optional[Dict[str, Any]], List[str]]:
    """Validate configuration update data.

    Returns:
        tuple: (is_valid, error_response, unknown_fields)
               If valid, error_response is None
               If invalid, error_response contains error details
               unknown_fields is a list of paths to unknown fields that were ignored
    """
    unknown_fields = []

    try:
        # Check for unknown top-level sections
        for section in updates:
            if section not in ["learning", "audio", "display"]:
                unknown_fields.append(section)

        # Check for metadata updates (read-only)
        if "metadata" in updates:
            return False, {
                "success": False,
                "error": {
                    "code": "READ_ONLY_FIELD",
                    "message": "Metadata fields are read-only and cannot be directly modified",
                    "details": {
                        "field": "metadata"
                    }
                }
            }, []

        # Validate learning section
        if "learning" in updates:
            learning = updates["learning"]
            if not isinstance(learning, dict):
                return False, _validation_error("learning", learning, "Must be an object"), []

            # Check for unknown fields in learning section
            known_learning_fields = ["currentLevel", "userProficiency", "journeyAutoAdvance", "showMotivationalBreaks"]
            for field in learning:
                if field not in known_learning_fields:
                    unknown_fields.append(f"learning.{field}")

            if "currentLevel" in learning:
                level = learning["currentLevel"]
                if not isinstance(level, int) or level < 1 or level > 20:
                    return False, _validation_error(
                        "learning.currentLevel",
                        level,
                        "Must be an integer between 1 and 20"
                    ), []

            if "userProficiency" in learning:
                prof = learning["userProficiency"]
                if prof not in VALID_PROFICIENCY_LEVELS:
                    return False, _validation_error(
                        "learning.userProficiency",
                        prof,
                        f"Must be one of: {', '.join(VALID_PROFICIENCY_LEVELS)}",
                        {"allowedValues": VALID_PROFICIENCY_LEVELS}
                    ), []

            if "journeyAutoAdvance" in learning:
                if not isinstance(learning["journeyAutoAdvance"], bool):
                    return False, _validation_error(
                        "learning.journeyAutoAdvance",
                        learning["journeyAutoAdvance"],
                        "Must be a boolean"
                    ), []

            if "showMotivationalBreaks" in learning:
                if not isinstance(learning["showMotivationalBreaks"], bool):
                    return False, _validation_error(
                        "learning.showMotivationalBreaks",
                        learning["showMotivationalBreaks"],
                        "Must be a boolean"
                    ), []

        # Validate audio section
        if "audio" in updates:
            audio = updates["audio"]
            if not isinstance(audio, dict):
                return False, _validation_error("audio", audio, "Must be an object"), []

            # Check for unknown fields in audio section
            known_audio_fields = ["enabled", "selectedVoice", "downloadOnWiFiOnly"]
            for field in audio:
                if field not in known_audio_fields:
                    unknown_fields.append(f"audio.{field}")

            if "enabled" in audio:
                if not isinstance(audio["enabled"], bool):
                    return False, _validation_error(
                        "audio.enabled",
                        audio["enabled"],
                        "Must be a boolean"
                    ), []

            if "selectedVoice" in audio:
                voice = audio["selectedVoice"]
                if voice is not None and not isinstance(voice, str):
                    return False, _validation_error(
                        "audio.selectedVoice",
                        voice,
                        "Must be a string or null"
                    ), []
                # Convert null to "random"
                if voice is None:
                    audio["selectedVoice"] = "random"

            if "downloadOnWiFiOnly" in audio:
                if not isinstance(audio["downloadOnWiFiOnly"], bool):
                    return False, _validation_error(
                        "audio.downloadOnWiFiOnly",
                        audio["downloadOnWiFiOnly"],
                        "Must be a boolean"
                    ), []

        # Validate display section
        if "display" in updates:
            display = updates["display"]
            if not isinstance(display, dict):
                return False, _validation_error("display", display, "Must be an object"), []

            # Check for unknown fields in display section
            known_display_fields = ["colorScheme", "showGrammarInterstitials"]
            for field in display:
                if field not in known_display_fields:
                    unknown_fields.append(f"display.{field}")

            if "colorScheme" in display:
                scheme = display["colorScheme"]
                if scheme not in VALID_COLOR_SCHEMES:
                    return False, _validation_error(
                        "display.colorScheme",
                        scheme,
                        f"Must be one of: {', '.join(VALID_COLOR_SCHEMES)}",
                        {"allowedValues": VALID_COLOR_SCHEMES}
                    ), []

            if "showGrammarInterstitials" in display:
                if not isinstance(display["showGrammarInterstitials"], bool):
                    return False, _validation_error(
                        "display.showGrammarInterstitials",
                        display["showGrammarInterstitials"],
                        "Must be a boolean"
                    ), []

        return True, None, unknown_fields

    except Exception as e:
        logger.error(f"Error during validation: {str(e)}")
        return False, {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"Validation error: {str(e)}"
            }
        }, []


def _validation_error(field: str, value: Any, message: str, extra_details: Optional[Dict] = None) -> Dict[str, Any]:
    """Create a validation error response."""
    details = {
        "field": field,
        "value": value
    }
    if extra_details:
        details.update(extra_details)

    return {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": message,
            "details": details
        }
    }


def _apply_updates(current_config: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply partial updates to current configuration, filtering out unknown fields."""
    updated_config = _deep_copy_config(current_config)

    # Define known fields for each section
    known_fields = {
        "learning": ["currentLevel", "userProficiency", "journeyAutoAdvance", "showMotivationalBreaks"],
        "audio": ["enabled", "selectedVoice", "downloadOnWiFiOnly"],
        "display": ["colorScheme", "showGrammarInterstitials"]
    }

    # Apply updates to each section, filtering unknown fields
    for section in ["learning", "audio", "display"]:
        if section in updates and isinstance(updates[section], dict):
            if section not in updated_config:
                updated_config[section] = {}

            # Only update known fields
            for field, value in updates[section].items():
                if field in known_fields[section]:
                    updated_config[section][field] = value

    return updated_config


##############################################################################
# API Endpoints
##############################################################################

@trakaido_bp.route("/api/trakaido/userconfig/", methods=["GET"])
@require_auth
def get_user_config():
    """Get user configuration.

    Returns the complete user configuration including learning preferences,
    audio settings, display preferences, and metadata.
    """
    try:
        user = g.user
        language = request.args.get("language", "lithuanian")

        config = load_user_config(str(user.id), language)

        return jsonify(config), 200

    except Exception as e:
        logger.error(f"Error getting user config: {str(e)}")
        return jsonify({
            "success": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": "Internal server error"
            }
        }), 500


@trakaido_bp.route("/api/trakaido/userconfig/", methods=["PATCH"])
@require_auth
def update_user_config():
    """Update user configuration.

    Accepts partial updates - only the fields provided will be updated.
    All other fields remain unchanged.
    Unknown fields are ignored and a warning is returned.
    """
    try:
        user = g.user
        language = request.args.get("language", "lithuanian")

        # Get request data
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request must be JSON"
                }
            }), 400

        updates = request.get_json()

        # Validate updates
        is_valid, error_response, unknown_fields = validate_config_update(updates)
        if not is_valid:
            return jsonify(error_response), 422

        # Load current config
        current_config = load_user_config(str(user.id), language)

        # Apply updates (unknown fields are already filtered out)
        updated_config = _apply_updates(current_config, updates)

        # Save updated config
        if not save_user_config(str(user.id), updated_config, language):
            return jsonify({
                "success": False,
                "error": {
                    "code": "SAVE_FAILED",
                    "message": "Failed to save configuration"
                }
            }), 500

        # Build response
        response = {
            "success": True,
            "message": "User configuration updated successfully",
            "config": updated_config
        }

        # Add warning if unknown fields were present
        if unknown_fields:
            response["warning"] = {
                "code": "UNKNOWN_FIELDS_IGNORED",
                "message": "Some fields were not recognized and have been ignored",
                "ignoredFields": unknown_fields
            }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error updating user config: {str(e)}")
        return jsonify({
            "success": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": "Internal server error"
            }
        }), 500
