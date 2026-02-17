"""Activity stats management for Lithuanian language learning."""

# Standard library imports
from datetime import datetime
from typing import Any, Dict

# Third-party imports
from flask import g, jsonify, request
from flask.typing import ResponseReturnValue

# Local application imports
from atacama.decorators.auth import require_auth
from trakaido.blueprints.shared import trakaido_bp, logger
from trakaido.blueprints.date_utils import get_current_day_key
from trakaido.blueprints.nonce_utils import load_nonces, save_nonces, check_nonce_duplicates
from trakaido.blueprints.stats_schema import (
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
    create_empty_word_stats,
    validate_and_normalize_word_stats,
    merge_word_stats,
)
from trakaido.blueprints.stats_backend import (
    get_journey_stats,
    ensure_daily_snapshots,
    calculate_daily_progress,
    calculate_weekly_progress,
    calculate_monthly_progress,
)
from trakaido.blueprints.stats_metrics import compute_member_summary

##############################################################################

# API Documentation for journey stats endpoints
USERSTATS_API_DOCS = {
    "GET /api/trakaido/journeystats/": "Get all journey stats for authenticated user",
    "GET /api/trakaido/journeystats/summary": "Get normalized dashboard summary for authenticated user",
    "PUT /api/trakaido/journeystats/": "Save all journey stats for authenticated user",
    "POST /api/trakaido/journeystats/word": "Update stats for a specific word",
    "GET /api/trakaido/journeystats/word/{wordKey}": "Get stats for a specific word",
    "POST /api/trakaido/journeystats/increment": "Increment stats for a single question with nonce",
    "POST /api/trakaido/journeystats/bulk_increment": "Bulk increment stats for multiple questions with nonces",
    "GET /api/trakaido/journeystats/daily": "Get daily stats (today's progress)",
    "GET /api/trakaido/journeystats/weekly": "Get weekly stats (7-day progress)",
    "GET /api/trakaido/journeystats/monthly": "Get monthly stats with daily breakdown (questions answered, exposed words count, newly exposed words) and monthly aggregate",
    "POST /api/trakaido/journeystats/merge": "Merge local (demo mode) stats with server stats - for mobile clients syncing after first login",
}

##############################################################################
# Increment Helper Functions
##############################################################################


def parse_stat_type(stat_type: str) -> tuple[str, str, bool]:
    """Parse stat type and return (category, activity, is_contextual).

    Expects new format (e.g., "directPractice.multipleChoice_targetToEnglish").

    Returns:
        tuple: (category, activity, is_contextual)

    Raises:
        ValueError: If stat_type is invalid
    """
    if "." not in stat_type:
        raise ValueError(
            f"Invalid stat type format: {stat_type}. Expected format: 'category.activity'"
        )

    parts = stat_type.split(".", 1)
    category = parts[0]
    activity = parts[1]
    is_contextual = False

    if category == "contextualExposure":
        is_contextual = True
        if activity not in CONTEXTUAL_EXPOSURE_TYPES:
            raise ValueError(f"Invalid contextual exposure type: {activity}")
    elif category == "directPractice":
        if activity not in DIRECT_PRACTICE_TYPES:
            raise ValueError(f"Invalid direct practice type: {activity}")
    else:
        raise ValueError(
            f"Invalid category: {category}. Must be 'directPractice' or 'contextualExposure'"
        )

    return category, activity, is_contextual


def increment_word_stat(
    journey_stats: "JourneyStats",
    word_key: str,
    category: str,
    activity: str,
    correct: bool,
    is_contextual: bool,
    current_timestamp: int,
) -> Dict[str, Any]:
    """Increment stats for a single word and update timestamps.

    Args:
        journey_stats: JourneyStats object to update
        word_key: Key for the word being updated
        category: Category ("directPractice" or "contextualExposure")
        activity: Activity type within the category
        correct: Whether the answer was correct
        is_contextual: Whether this is contextual exposure (affects timestamp updates)
        current_timestamp: Current timestamp in milliseconds

    Returns:
        The updated word stats dictionary
    """
    # Initialize word stats if they don't exist (use new schema)
    if word_key not in journey_stats.stats["stats"]:
        journey_stats.stats["stats"][word_key] = create_empty_word_stats()

    word_stats = journey_stats.stats["stats"][word_key]

    # Ensure the word stats have the new schema structure
    if (
        "directPractice" not in word_stats
        or "contextualExposure" not in word_stats
        or "practiceHistory" not in word_stats
    ):
        # Migrate to new schema if needed
        word_stats = validate_and_normalize_word_stats(word_stats)
        journey_stats.stats["stats"][word_key] = word_stats

    # Increment the appropriate counter
    if category not in word_stats:
        if category == "directPractice":
            word_stats[category] = {
                act: {"correct": 0, "incorrect": 0} for act in DIRECT_PRACTICE_TYPES
            }
        else:
            word_stats[category] = {
                act: {"correct": 0, "incorrect": 0} for act in CONTEXTUAL_EXPOSURE_TYPES
            }

    if activity not in word_stats[category]:
        word_stats[category][activity] = {"correct": 0, "incorrect": 0}

    if correct:
        word_stats[category][activity]["correct"] += 1
    else:
        word_stats[category][activity]["incorrect"] += 1

    # Update timestamps based on activity type
    if "practiceHistory" not in word_stats:
        word_stats["practiceHistory"] = {
            "lastSeen": None,
            "lastCorrectAnswer": None,
            "lastIncorrectAnswer": None,
        }

    # Always update lastSeen
    word_stats["practiceHistory"]["lastSeen"] = current_timestamp

    # For direct practice: update lastCorrectAnswer or lastIncorrectAnswer
    # For contextual exposure (sentences): only update lastSeen
    if not is_contextual:
        if correct:
            word_stats["practiceHistory"]["lastCorrectAnswer"] = current_timestamp
        else:
            word_stats["practiceHistory"]["lastIncorrectAnswer"] = current_timestamp

    # Mark word as exposed
    word_stats["exposed"] = True

    return word_stats


##############################################################################
# Journey Stats API Routes
##############################################################################
@trakaido_bp.route("/api/trakaido/journeystats/", methods=["GET"])
@require_auth
def get_all_journey_stats() -> ResponseReturnValue:
    """Get all journey stats for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        journey_stats = get_journey_stats(user_id, language)

        # Optional shape extension used by dashboard surfaces that need
        # normalized summary metrics alongside raw per-word stats.
        include_summary = request.args.get("includeSummary", "false").lower() == "true"
        if include_summary:
            payload = dict(journey_stats.stats)
            payload["summary"] = compute_member_summary(user_id, language)
            return jsonify(payload)

        return jsonify(journey_stats.stats)
    except Exception as e:
        logger.error(f"Error getting all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/summary", methods=["GET"])
@require_auth
def get_member_stats_summary() -> ResponseReturnValue:
    """Get normalized summary metrics for the authenticated user dashboard."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        return jsonify(compute_member_summary(user_id, language))
    except Exception as e:
        logger.error(f"Error getting journey stats summary: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/", methods=["PUT"])
@require_auth
def save_all_journey_stats() -> ResponseReturnValue:
    """Save all journey stats for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        data = request.get_json()

        if not data or "stats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'stats' field."}), 400

        journey_stats = get_journey_stats(user_id, language)
        journey_stats.stats = data
        if journey_stats.save_with_daily_update():
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to save journey stats"}), 500
    except Exception as e:
        logger.error(f"Error saving all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/word", methods=["POST"])
@require_auth
def update_word_stats() -> ResponseReturnValue:
    """Update stats for a specific word for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        data = request.get_json()

        if not data or "wordKey" not in data or "wordStats" not in data:
            return (
                jsonify(
                    {"error": "Invalid request body. Expected 'wordKey' and 'wordStats' fields."}
                ),
                400,
            )

        word_key = data["wordKey"]
        word_stats = data["wordStats"]

        journey_stats = get_journey_stats(user_id, language)
        journey_stats.set_word_stats(word_key, word_stats)

        if journey_stats.save_with_daily_update():
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update word stats"}), 500
    except Exception as e:
        logger.error(f"Error updating word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/word/<word_key>", methods=["GET"])
@require_auth
def get_word_stats(word_key: str) -> ResponseReturnValue:
    """Get stats for a specific word for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        journey_stats = get_journey_stats(user_id, language)
        word_stats = journey_stats.get_word_stats(word_key)
        return jsonify({"wordStats": word_stats})
    except Exception as e:
        logger.error(f"Error getting word stats for '{word_key}': {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/increment", methods=["POST"])
@require_auth
def increment_word_stats() -> ResponseReturnValue:
    """Increment stats for a single question with nonce protection."""
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

        if not isinstance(correct, bool):
            return jsonify({"error": "Field 'correct' must be a boolean"}), 400

        if not isinstance(nonce, str) or not nonce.strip():
            return jsonify({"error": "Field 'nonce' must be a non-empty string"}), 400

        # Parse stat type using helper function
        try:
            category, activity, is_contextual = parse_stat_type(stat_type)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        current_day = get_current_day_key()

        # Check if nonce has already been used (today or yesterday)
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({"error": "Nonce already used"}), 409

        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id, language):
            return jsonify({"error": "Failed to initialize daily stats"}), 500

        # Load current overall stats
        journey_stats = get_journey_stats(user_id, language)

        # Increment the word stats using helper function
        current_timestamp = int(datetime.now().timestamp() * 1000)
        word_stats = increment_word_stat(
            journey_stats, word_key, category, activity, correct, is_contextual, current_timestamp
        )

        # Save updated stats
        if not journey_stats.save_with_daily_update():
            return jsonify({"error": "Failed to save stats"}), 500

        # Add nonce to today's used nonces
        used_nonces = load_nonces(user_id, current_day, language)
        used_nonces.add(nonce)
        if not save_nonces(user_id, current_day, used_nonces, language):
            logger.warning(
                f"Failed to save nonce for user {user_id} day {current_day} language {language}"
            )

        return jsonify(
            {
                "success": True,
                "wordKey": word_key,
                "statType": stat_type,
                "correct": correct,
                "newStats": word_stats[category][activity],
            }
        )

    except Exception as e:
        logger.error(f"Error incrementing word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/bulk_increment", methods=["POST"])
@require_auth
def bulk_increment_word_stats() -> ResponseReturnValue:
    """Bulk increment stats for multiple questions with nonce protection.

    Request body should contain:
    {
        "nonce": "unique-batch-nonce",
        "increments": [
            {
                "wordKey": "word1",
                "statType": "multipleChoice",
                "correct": true
            },
            ...
        ]
    }

    Returns:
    {
        "success": true,
        "processed": 10,
        "failed": 0,
        "results": [
            {"index": 0, "status": "success"},
            {"index": 1, "status": "failed", "reason": "Invalid stat type: foo"},
            ...
        ]
    }
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()

        # Validate request body
        if not data or "increments" not in data or "nonce" not in data:
            return (
                jsonify(
                    {"error": "Invalid request body. Expected 'nonce' and 'increments' fields."}
                ),
                400,
            )

        nonce = data["nonce"]
        increments = data["increments"]

        # Validate nonce
        if not isinstance(nonce, str) or not nonce.strip():
            return jsonify({"error": "Field 'nonce' must be a non-empty string"}), 400

        if not isinstance(increments, list):
            return jsonify({"error": "Field 'increments' must be an array"}), 400

        if len(increments) == 0:
            return jsonify({"error": "Field 'increments' cannot be empty"}), 400

        if len(increments) > 1000:
            return jsonify({"error": "Maximum 1000 increments per request"}), 400

        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        current_day = get_current_day_key()

        # Check if this batch nonce has already been used
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({"error": "Batch nonce already used"}), 409

        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id, language):
            return jsonify({"error": "Failed to initialize daily stats"}), 500

        # Load journey stats once
        journey_stats = get_journey_stats(user_id, language)

        processed_count = 0
        failed_count = 0
        results = []
        current_timestamp = int(datetime.now().timestamp() * 1000)

        # Process each increment
        for idx, increment in enumerate(increments):
            try:
                # Validate individual increment
                required_fields = ["wordKey", "statType", "correct"]
                missing_fields = [field for field in required_fields if field not in increment]

                if missing_fields:
                    failed_count += 1
                    results.append(
                        {
                            "index": idx,
                            "status": "failed",
                            "reason": f"Missing fields: {', '.join(missing_fields)}",
                        }
                    )
                    continue

                word_key = increment["wordKey"]
                stat_type = increment["statType"]
                correct = increment["correct"]

                # Validate correct field
                if not isinstance(correct, bool):
                    failed_count += 1
                    results.append(
                        {"index": idx, "status": "failed", "reason": "'correct' must be a boolean"}
                    )
                    continue

                # Parse stat type using helper function
                try:
                    category, activity, is_contextual = parse_stat_type(stat_type)
                except ValueError as e:
                    failed_count += 1
                    results.append({"index": idx, "status": "failed", "reason": str(e)})
                    continue

                # Increment the word stats using helper function
                increment_word_stat(
                    journey_stats,
                    word_key,
                    category,
                    activity,
                    correct,
                    is_contextual,
                    current_timestamp,
                )

                processed_count += 1
                results.append({"index": idx, "status": "success"})

            except Exception as e:
                failed_count += 1
                results.append({"index": idx, "status": "failed", "reason": str(e)})
                logger.error(f"Error processing increment {idx}: {str(e)}")

        # Save updated stats if any were processed
        if processed_count > 0:
            if not journey_stats.save_with_daily_update():
                return jsonify({"error": "Failed to save stats after processing"}), 500

            # Save the batch nonce
            language = g.current_language if hasattr(g, "current_language") else "lithuanian"
            used_nonces = load_nonces(user_id, current_day, language)
            used_nonces.add(nonce)
            if not save_nonces(user_id, current_day, used_nonces, language):
                logger.warning(
                    f"Failed to save nonce for user {user_id} day {current_day} language {language}"
                )

        return jsonify(
            {
                "success": True,
                "processed": processed_count,
                "failed": failed_count,
                "results": results,
            }
        )

    except Exception as e:
        logger.error(f"Error in bulk increment: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/daily", methods=["GET"])
@require_auth
def get_daily_stats() -> ResponseReturnValue:
    """Get daily stats (today's progress) for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        daily_progress = calculate_daily_progress(user_id, language)

        if "error" in daily_progress:
            return jsonify(daily_progress), 500

        return jsonify(daily_progress)
    except Exception as e:
        logger.error(f"Error getting daily stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/weekly", methods=["GET"])
@require_auth
def get_weekly_stats() -> ResponseReturnValue:
    """Get weekly stats (7-day progress) for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        weekly_progress = calculate_weekly_progress(user_id, language)

        if "error" in weekly_progress:
            return jsonify(weekly_progress), 500

        return jsonify(weekly_progress)
    except Exception as e:
        logger.error(f"Error getting weekly stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/monthly", methods=["GET"])
@require_auth
def get_monthly_stats() -> ResponseReturnValue:
    """
    Get monthly stats for the authenticated user.

    Returns:
    - monthlyAggregate: Aggregate stats for the entire 30-day period
    - dailyData: Per-day stats showing questions answered, exposed words count, and newly exposed words
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        monthly_progress = calculate_monthly_progress(user_id, language)

        if "error" in monthly_progress:
            return jsonify(monthly_progress), 500

        return jsonify(monthly_progress)
    except Exception as e:
        logger.error(f"Error getting monthly stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/journeystats/merge", methods=["POST"])
@require_auth
def merge_local_stats() -> ResponseReturnValue:
    """Merge local (demo mode) stats with server stats.

    This endpoint is called when a mobile client that was previously in demo mode
    (with locally stored stats) first connects to an account. It bulk-accepts
    all local stats, merges them with existing server stats, and returns the
    merged result for the client to download.

    Merge logic:
    - Counters (correct/incorrect): Take MAXIMUM to prevent double-counting
    - Timestamps: Take MAXIMUM (most recent activity)
    - Boolean flags (exposed, markedAsKnown): Logical OR

    Request body:
    {
        "nonce": "unique-merge-operation-id",
        "localStats": {
            "stats": {
                "wordKey1": { <word stats object> },
                ...
            }
        }
    }

    Returns:
    {
        "success": true,
        "merged": {
            "stats": { <merged stats> }
        },
        "summary": {
            "localWordCount": 45,
            "serverWordCount": 32,
            "mergedWordCount": 58,
            "newWordsFromLocal": 26,
            "updatedWords": 19
        }
    }
    """
    try:
        user_id = str(g.user.id)
        data = request.get_json()

        # Validate request body
        if not data:
            return jsonify({"error": "Invalid request body"}), 400

        if "nonce" not in data:
            return jsonify({"error": "Missing required field: nonce"}), 400

        if "localStats" not in data:
            return jsonify({"error": "Missing required field: localStats"}), 400

        nonce = data["nonce"]
        local_stats_data = data["localStats"]

        if not isinstance(nonce, str) or not nonce.strip():
            return jsonify({"error": "Field 'nonce' must be a non-empty string"}), 400

        if not isinstance(local_stats_data, dict) or "stats" not in local_stats_data:
            return jsonify({"error": "Field 'localStats' must contain a 'stats' object"}), 400

        local_word_stats = local_stats_data.get("stats", {})
        if not isinstance(local_word_stats, dict):
            return jsonify({"error": "Field 'localStats.stats' must be an object"}), 400

        language = g.current_language if hasattr(g, "current_language") else "lithuanian"
        current_day = get_current_day_key()

        # Check if this merge nonce has already been used
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({"error": "Merge nonce already used"}), 409

        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id, language):
            return jsonify({"error": "Failed to initialize daily stats"}), 500

        # Load current server stats
        journey_stats = get_journey_stats(user_id, language)
        server_word_stats = journey_stats.stats.get("stats", {})

        # Track merge statistics
        local_word_count = len(local_word_stats)
        server_word_count = len(server_word_stats)
        new_words_from_local = 0
        updated_words = 0

        # Merge each word from local stats
        all_word_keys = set(server_word_stats.keys()) | set(local_word_stats.keys())
        merged_stats: Dict[str, Any] = {"stats": {}}

        for word_key in all_word_keys:
            server_word = server_word_stats.get(word_key, {})
            local_word = local_word_stats.get(word_key, {})

            # Merge the word stats
            merged_word = merge_word_stats(server_word, local_word)
            merged_stats["stats"][word_key] = merged_word

            # Track statistics
            if word_key not in server_word_stats:
                new_words_from_local += 1
            elif word_key in local_word_stats:
                # Word existed on server and was also in local - check if updated
                if server_word != merged_word:
                    updated_words += 1

        merged_word_count = len(merged_stats["stats"])

        # Save merged stats
        journey_stats.stats = merged_stats
        if not journey_stats.save_with_daily_update():
            return jsonify({"error": "Failed to save merged stats"}), 500

        # Save the merge nonce to prevent duplicate merges
        used_nonces = load_nonces(user_id, current_day, language)
        used_nonces.add(nonce)
        if not save_nonces(user_id, current_day, used_nonces, language):
            logger.warning(
                f"Failed to save merge nonce for user {user_id} day {current_day} language {language}"
            )

        logger.info(
            f"Stats merge completed for user {user_id} language {language}: "
            f"local={local_word_count}, server={server_word_count}, merged={merged_word_count}, "
            f"new={new_words_from_local}, updated={updated_words}"
        )

        return jsonify(
            {
                "success": True,
                "merged": merged_stats,
                "summary": {
                    "localWordCount": local_word_count,
                    "serverWordCount": server_word_count,
                    "mergedWordCount": merged_word_count,
                    "newWordsFromLocal": new_words_from_local,
                    "updatedWords": updated_words,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error merging local stats: {str(e)}")
        return jsonify({"error": str(e)}), 500
