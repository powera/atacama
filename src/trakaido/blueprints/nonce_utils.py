"""Nonce management utilities for Trakaido stats."""

# Standard library imports
import json
import os
from typing import List

# Local application imports
import constants
from trakaido.blueprints.shared import logger
from trakaido.blueprints.date_utils import get_current_day_key, get_yesterday_day_key


def get_nonce_file_path(user_id: str, day_key: str, language: str = "lithuanian") -> str:
    """Get the file path for a user's nonce tracking file."""
    daily_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language, "daily")
    os.makedirs(daily_dir, exist_ok=True)
    return os.path.join(daily_dir, f"{day_key}_nonces.json")


def load_nonces(user_id: str, day_key: str, language: str = "lithuanian") -> set:
    """Load used nonces for a specific day."""
    try:
        nonce_file = get_nonce_file_path(user_id, day_key, language)
        if not os.path.exists(nonce_file):
            return set()

        with open(nonce_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return set(data.get("nonces", []))
    except Exception as e:
        logger.error(
            f"Error loading nonces for user {user_id} day {day_key} language {language}: {str(e)}"
        )
        return set()


def save_nonces(user_id: str, day_key: str, nonces: set, language: str = "lithuanian") -> bool:
    """Save used nonces for a specific day."""
    try:
        user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language)
        os.makedirs(user_data_dir, exist_ok=True)
        nonce_file = get_nonce_file_path(user_id, day_key, language)

        with open(nonce_file, "w", encoding="utf-8") as f:
            json.dump({"nonces": list(nonces)}, f)

        return True
    except Exception as e:
        logger.error(
            f"Error saving nonces for user {user_id} day {day_key} language {language}: {str(e)}"
        )
        return False


def get_all_nonce_files(user_id: str, language: str = "lithuanian") -> List[str]:
    """Get all nonce files for a user."""
    try:
        daily_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language, "daily")
        if not os.path.exists(daily_dir):
            return []

        nonce_files = []
        for filename in os.listdir(daily_dir):
            if filename.endswith("_nonces.json"):
                date_part = filename[:-12]  # Remove "_nonces.json"
                if len(date_part) == 10 and date_part.count("-") == 2:
                    nonce_files.append(date_part)

        return sorted(nonce_files)
    except Exception as e:
        logger.error(f"Error getting nonce files for user {user_id} language {language}: {str(e)}")
        return []


def cleanup_old_nonce_files(user_id: str, language: str = "lithuanian") -> bool:
    """Remove nonce files older than today and yesterday."""
    try:
        current_day = get_current_day_key()
        yesterday_day = get_yesterday_day_key()
        keep_dates = {current_day, yesterday_day}

        all_nonce_dates = get_all_nonce_files(user_id, language)
        removed_count = 0

        for date_str in all_nonce_dates:
            if date_str not in keep_dates:
                nonce_file = get_nonce_file_path(user_id, date_str, language)
                try:
                    if os.path.exists(nonce_file):
                        os.remove(nonce_file)
                        removed_count += 1
                        logger.debug(
                            f"Removed old nonce file for user {user_id} date {date_str} language {language}"
                        )
                except Exception as e:
                    logger.error(f"Error removing nonce file {nonce_file}: {str(e)}")

        if removed_count > 0:
            logger.info(
                f"Cleaned up {removed_count} old nonce files for user {user_id} language {language}"
            )

        return True
    except Exception as e:
        logger.error(
            f"Error cleaning up old nonce files for user {user_id} language {language}: {str(e)}"
        )
        return False


def check_nonce_duplicates(user_id: str, nonce: str, language: str = "lithuanian") -> bool:
    """Check if nonce exists in today's or yesterday's nonce lists."""
    try:
        current_day = get_current_day_key()
        yesterday_day = get_yesterday_day_key()

        # Check today's nonces
        today_nonces = load_nonces(user_id, current_day, language)
        if nonce in today_nonces:
            logger.warning(
                f"Duplicate nonce '{nonce}' found in today's list for user {user_id} language {language}"
            )
            return True

        # Check yesterday's nonces
        yesterday_nonces = load_nonces(user_id, yesterday_day, language)
        if nonce in yesterday_nonces:
            logger.warning(
                f"Duplicate nonce '{nonce}' found in yesterday's list for user {user_id} language {language}"
            )
            return True

        return False
    except Exception as e:
        logger.error(
            f"Error checking nonce duplicates for user {user_id} language {language}: {str(e)}"
        )
        return True  # Return True to be safe and reject the nonce
