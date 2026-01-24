"""Grammar statistics management for Trakaido language learning.

Tracks user exposure to grammar interstitial lessons, including view counts
and timestamps for each grammar concept.
"""

# Standard library imports
import json
import os
import re
import time
from typing import Any, Dict, Optional

# Third-party imports
from flask import g, jsonify, request
from flask.typing import ResponseReturnValue

# Local application imports
import constants
from atacama.decorators.auth import require_auth
from trakaido.blueprints.shared import trakaido_bp, logger, ensure_user_data_dir
from trakaido.blueprints.date_utils import get_current_day_key
from trakaido.blueprints.nonce_utils import (
    load_nonces,
    save_nonces,
    check_nonce_duplicates
)

##############################################################################
# Constants and Validation
##############################################################################

# Concept ID validation pattern: lowercase letters and hyphens only
# Must start and end with a letter, max 100 chars
# Single letter concepts are also valid
CONCEPT_ID_PATTERN = re.compile(r'^[a-z]([a-z\-]*[a-z])?$')
MAX_CONCEPT_ID_LENGTH = 100


def validate_concept_id(concept_id: str) -> bool:
    """Validate a grammar concept ID.

    Valid concept IDs:
    - Contain only lowercase letters (a-z) and hyphens
    - Start and end with a letter
    - Maximum 100 characters
    - Single letter concepts are valid

    Args:
        concept_id: The concept ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not concept_id or not isinstance(concept_id, str):
        return False
    if len(concept_id) > MAX_CONCEPT_ID_LENGTH:
        return False
    return bool(CONCEPT_ID_PATTERN.match(concept_id))


def validate_concept_stats(stats: Dict[str, Any]) -> bool:
    """Validate a single concept's stats object.

    Args:
        stats: Dict with viewCount and lastViewedAt

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(stats, dict):
        return False

    # viewCount must be a non-negative integer
    view_count = stats.get("viewCount")
    if not isinstance(view_count, int) or view_count < 0:
        return False

    # lastViewedAt must be a positive number or null
    last_viewed = stats.get("lastViewedAt")
    if last_viewed is not None:
        if not isinstance(last_viewed, (int, float)) or last_viewed <= 0:
            return False

    return True


##############################################################################
# Storage Class
##############################################################################

class GrammarStats:
    """Manages access to a user's grammar statistics file.

    Grammar stats track exposure to grammar interstitial lessons:
    - viewCount: How many times each lesson has been shown
    - lastViewedAt: When the lesson was most recently seen (ms timestamp)
    """

    def __init__(self, user_id: str, language: str = "lithuanian"):
        self.user_id = str(user_id)
        self.language = language
        self._stats: Optional[Dict[str, Any]] = None
        self._loaded = False

    @property
    def file_path(self) -> str:
        """Get the file path for this user's grammar stats file."""
        user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", self.user_id, self.language)
        os.makedirs(user_data_dir, exist_ok=True)
        return os.path.join(user_data_dir, "grammar_stats.json")

    def load(self) -> bool:
        """Load the stats from the file.

        Returns:
            True if loaded successfully (including empty stats for new users)
        """
        try:
            if not os.path.exists(self.file_path):
                logger.debug(f"No grammar stats file found at {self.file_path}, returning empty stats")
                self._stats = {"stats": {}}
                self._loaded = True
                return True

            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict) and "stats" in data:
                self._stats = data
            else:
                self._stats = {"stats": {}}

            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading grammar stats for user {self.user_id}: {str(e)}")
            self._stats = {"stats": {}}
            self._loaded = True
            return False

    def save(self) -> bool:
        """Save the current stats to the file.

        Returns:
            True if saved successfully
        """
        if not self._loaded or self._stats is None:
            logger.warning(f"Attempting to save unloaded grammar stats for user {self.user_id}")
            return False

        try:
            ensure_user_data_dir(self.user_id, self.language)

            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            logger.error(f"Error saving grammar stats to {self.file_path}: {str(e)}")
            return False

    @property
    def stats(self) -> Dict[str, Any]:
        """Get the stats dictionary. Loads from file if not already loaded."""
        if not self._loaded:
            self.load()
        return self._stats or {"stats": {}}

    @stats.setter
    def stats(self, value: Dict[str, Any]):
        """Set the stats dictionary."""
        self._stats = value
        self._loaded = True

    def get_concept_stats(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get stats for a specific concept.

        Args:
            concept_id: The grammar concept ID

        Returns:
            Stats dict with viewCount and lastViewedAt, or None if not found
        """
        return self.stats["stats"].get(concept_id)

    def record_view(self, concept_id: str) -> Dict[str, Any]:
        """Record a view for a grammar concept.

        Increments viewCount and updates lastViewedAt timestamp.

        Args:
            concept_id: The grammar concept ID

        Returns:
            Updated stats for the concept
        """
        if not self._loaded:
            self.load()

        if self._stats is None:
            self._stats = {"stats": {}}

        if "stats" not in self._stats:
            self._stats["stats"] = {}

        current_timestamp = int(time.time() * 1000)  # milliseconds

        if concept_id in self._stats["stats"]:
            self._stats["stats"][concept_id]["viewCount"] += 1
            self._stats["stats"][concept_id]["lastViewedAt"] = current_timestamp
        else:
            self._stats["stats"][concept_id] = {
                "viewCount": 1,
                "lastViewedAt": current_timestamp
            }

        return self._stats["stats"][concept_id]


##############################################################################
# API Routes
##############################################################################

@trakaido_bp.route('/api/trakaido/grammarstats/', methods=['GET'])
@require_auth
def get_grammar_stats() -> ResponseReturnValue:
    """Get all grammar stats for the authenticated user.

    Returns:
        JSON response with {"stats": {...}} containing all concept stats
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"

        grammar_stats = GrammarStats(user_id, language)
        return jsonify(grammar_stats.stats)
    except Exception as e:
        logger.error(f"Error getting grammar stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/grammarstats/view', methods=['POST'])
@require_auth
def record_grammar_view() -> ResponseReturnValue:
    """Record a grammar lesson view with nonce protection.

    Request body:
        {"conceptId": "nominative-form", "nonce": "unique-string-12345"}

    Returns:
        200: {"success": true, "stats": {"viewCount": 4, "lastViewedAt": ...}}
        400: Invalid concept ID or missing fields
        409: Duplicate nonce (view already recorded)
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()

        # Validate request body
        if not data:
            return jsonify({"error": "Invalid request body"}), 400

        concept_id = data.get("conceptId")
        nonce = data.get("nonce")

        if not concept_id:
            return jsonify({"error": "Missing required field: conceptId"}), 400

        if not nonce:
            return jsonify({"error": "Missing required field: nonce"}), 400

        if not isinstance(nonce, str) or not nonce.strip():
            return jsonify({"error": "Field 'nonce' must be a non-empty string"}), 400

        if not validate_concept_id(concept_id):
            return jsonify({
                "error": f"Invalid concept ID: '{concept_id}'. Must be lowercase letters and hyphens only, max {MAX_CONCEPT_ID_LENGTH} chars."
            }), 400

        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        current_day = get_current_day_key()

        # Check if nonce has already been used (today or yesterday)
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({
                "error": "duplicate_nonce",
                "message": "This view has already been recorded"
            }), 409

        # Load and update grammar stats
        grammar_stats = GrammarStats(user_id, language)
        concept_stats = grammar_stats.record_view(concept_id)

        # Save updated stats
        if not grammar_stats.save():
            return jsonify({"error": "Failed to save grammar stats"}), 500

        # Save nonce to prevent duplicate views
        used_nonces = load_nonces(user_id, current_day, language)
        used_nonces.add(nonce)
        if not save_nonces(user_id, current_day, used_nonces, language):
            logger.warning(f"Failed to save nonce for user {user_id} day {current_day} language {language}")

        return jsonify({
            "success": True,
            "stats": concept_stats
        })

    except Exception as e:
        logger.error(f"Error recording grammar view: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/grammarstats/', methods=['PUT'])
@require_auth
def replace_grammar_stats() -> ResponseReturnValue:
    """Replace all grammar stats for the user (used for sync/restore).

    Request body:
        {"stats": {"nominative-form": {"viewCount": 3, "lastViewedAt": ...}, ...}}

    Returns:
        200: {"success": true}
        400: Invalid request body or stats format
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()

        # Validate request body
        if not data or "stats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'stats' field."}), 400

        incoming_stats = data["stats"]
        if not isinstance(incoming_stats, dict):
            return jsonify({"error": "Field 'stats' must be an object"}), 400

        # Validate all concept IDs and stats
        validated_stats: Dict[str, Any] = {}
        for concept_id, concept_stats in incoming_stats.items():
            if not validate_concept_id(concept_id):
                return jsonify({
                    "error": f"Invalid concept ID: '{concept_id}'. Must be lowercase letters and hyphens only."
                }), 400

            if not validate_concept_stats(concept_stats):
                return jsonify({
                    "error": f"Invalid stats for concept '{concept_id}'. Expected viewCount (non-negative int) and lastViewedAt (positive number or null)."
                }), 400

            validated_stats[concept_id] = {
                "viewCount": concept_stats["viewCount"],
                "lastViewedAt": concept_stats.get("lastViewedAt")
            }

        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"

        # Replace stats
        grammar_stats = GrammarStats(user_id, language)
        grammar_stats.stats = {"stats": validated_stats}

        if not grammar_stats.save():
            return jsonify({"error": "Failed to save grammar stats"}), 500

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Error replacing grammar stats: {str(e)}")
        return jsonify({"error": str(e)}), 500
