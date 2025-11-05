"""Activity stats management for Lithuanian language learning."""

# Standard library imports
import gzip
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Third-party imports
from flask import g, jsonify, request

# Local application imports
import constants
from web.decorators import require_auth
from .shared import *
from .date_utils import (
    get_current_day_key,
    get_yesterday_day_key,
    get_week_ago_day_key,
    get_30_days_ago_day_key,
    get_30_day_date_range
)
from .nonce_utils import (
    get_nonce_file_path,
    load_nonces,
    save_nonces,
    get_all_nonce_files,
    cleanup_old_nonce_files,
    check_nonce_duplicates
)

##############################################################################

# API Documentation for journey stats endpoints
USERSTATS_API_DOCS = {
    "GET /api/trakaido/journeystats/": "Get all journey stats for authenticated user",
    "PUT /api/trakaido/journeystats/": "Save all journey stats for authenticated user",
    "POST /api/trakaido/journeystats/word": "Update stats for a specific word",
    "GET /api/trakaido/journeystats/word/{wordKey}": "Get stats for a specific word",
    "POST /api/trakaido/journeystats/increment": "Increment stats for a single question with nonce",
    "POST /api/trakaido/journeystats/bulk_increment": "Bulk increment stats for multiple questions with nonces",
    "GET /api/trakaido/journeystats/daily": "Get daily stats (today's progress)",
    "GET /api/trakaido/journeystats/weekly": "Get weekly stats (7-day progress)",
    "GET /api/trakaido/journeystats/monthly": "Get monthly stats with daily breakdown (questions answered, exposed words count, newly exposed words) and monthly aggregate"
}

# Activity Stats related constants - NEW SCHEMA
# Direct practice activities (count toward proficiency)
DIRECT_PRACTICE_TYPES = {
    "multipleChoice_englishToTarget",
    "multipleChoice_targetToEnglish",
    "listening_targetAudioToTarget",
    "listening_targetAudioToEnglish",
    "typing_englishToTarget",
    "typing_targetToEnglish",
    "blitz_englishToTarget",
    "blitz_targetToEnglish"
}

# Contextual exposure activities (don't count toward proficiency)
CONTEXTUAL_EXPOSURE_TYPES = {"sentences", "flashcards"}

# All valid stat types
ALL_STAT_TYPES = DIRECT_PRACTICE_TYPES | CONTEXTUAL_EXPOSURE_TYPES

# Top-level fields
TOP_LEVEL_FIELDS = {"exposed", "markedAsKnown", "directPractice", "contextualExposure", "practiceHistory"}

def create_empty_word_stats() -> Dict[str, Any]:
    """Create an empty word stats object with the new schema structure."""
    return {
        "exposed": False,
        "directPractice": {
            activity: {"correct": 0, "incorrect": 0}
            for activity in DIRECT_PRACTICE_TYPES
        },
        "contextualExposure": {
            activity: {"correct": 0, "incorrect": 0}
            for activity in CONTEXTUAL_EXPOSURE_TYPES
        },
        "practiceHistory": {
            "lastSeen": None,
            "lastCorrectAnswer": None,
            "lastIncorrectAnswer": None
        }
    }


def validate_and_normalize_word_stats(word_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize word stats to ensure they match the new schema.

    This function:
    1. Ensures all required fields exist
    2. Filters out invalid fields
    """
    # Start with empty stats and fill in what we have
    normalized = create_empty_word_stats()

    # Copy exposed flag
    if "exposed" in word_stats and isinstance(word_stats["exposed"], bool):
        normalized["exposed"] = word_stats["exposed"]

    # Copy markedAsKnown if present
    if "markedAsKnown" in word_stats and isinstance(word_stats["markedAsKnown"], bool):
        normalized["markedAsKnown"] = word_stats["markedAsKnown"]

    # Copy directPractice stats
    if "directPractice" in word_stats and isinstance(word_stats["directPractice"], dict):
        for activity_type in DIRECT_PRACTICE_TYPES:
            if activity_type in word_stats["directPractice"]:
                activity_stats = word_stats["directPractice"][activity_type]
                if isinstance(activity_stats, dict):
                    correct = activity_stats.get("correct", 0)
                    incorrect = activity_stats.get("incorrect", 0)
                    if isinstance(correct, int) and isinstance(incorrect, int) and correct >= 0 and incorrect >= 0:
                        normalized["directPractice"][activity_type] = {
                            "correct": correct,
                            "incorrect": incorrect
                        }

    # Copy contextualExposure stats
    if "contextualExposure" in word_stats and isinstance(word_stats["contextualExposure"], dict):
        for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
            if activity_type in word_stats["contextualExposure"]:
                activity_stats = word_stats["contextualExposure"][activity_type]
                if isinstance(activity_stats, dict):
                    correct = activity_stats.get("correct", 0)
                    incorrect = activity_stats.get("incorrect", 0)
                    if isinstance(correct, int) and isinstance(incorrect, int) and correct >= 0 and incorrect >= 0:
                        normalized["contextualExposure"][activity_type] = {
                            "correct": correct,
                            "incorrect": incorrect
                        }

    # Copy practiceHistory timestamps
    if "practiceHistory" in word_stats and isinstance(word_stats["practiceHistory"], dict):
        for timestamp_field in ["lastSeen", "lastCorrectAnswer", "lastIncorrectAnswer"]:
            if timestamp_field in word_stats["practiceHistory"]:
                value = word_stats["practiceHistory"][timestamp_field]
                if value is None or (isinstance(value, (int, float)) and value > 0):
                    normalized["practiceHistory"][timestamp_field] = value

    return normalized


def user_has_activity_stats(user_id: str, language: str = "lithuanian") -> bool:
    """Check if a user has any activity stats."""
    try:
        journey_stats = JourneyStats(user_id, language)
        return not journey_stats.is_empty()
    except Exception as e:
        logger.error(f"Error checking activity stats for user {user_id}: {str(e)}")
        return False


##############################################################################
# Delta Calculation Helper Functions
##############################################################################

def calculate_progress_delta(current_stats: "DailyStats", baseline_stats: "DailyStats") -> Dict[str, Any]:
    """Calculate the delta between current stats and baseline stats.

    Returns a progress structure with deltas for:
    - directPractice activities
    - contextualExposure (sentences)
    - exposed words (new and total)
    """
    progress = {
        "directPractice": {activity: {"correct": 0, "incorrect": 0} for activity in DIRECT_PRACTICE_TYPES},
        "contextualExposure": {activity: {"correct": 0, "incorrect": 0} for activity in CONTEXTUAL_EXPOSURE_TYPES},
        "exposed": {"new": 0, "total": 0}
    }

    # Calculate progress for each word
    for word_key, current_word_stats in current_stats.stats["stats"].items():
        baseline_word_stats = baseline_stats.get_word_stats(word_key)

        # Count exposed words
        if current_word_stats.get("exposed", False):
            progress["exposed"]["total"] += 1
            # Count new exposed words (words that exist in current but not in baseline)
            if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                progress["exposed"]["new"] += 1

        # Calculate directPractice deltas
        if "directPractice" in current_word_stats:
            for activity_type in DIRECT_PRACTICE_TYPES:
                if activity_type in current_word_stats["directPractice"]:
                    current_activity = current_word_stats["directPractice"][activity_type]
                    current_correct = current_activity.get("correct", 0)
                    current_incorrect = current_activity.get("incorrect", 0)

                    baseline_correct = 0
                    baseline_incorrect = 0
                    if (baseline_word_stats and "directPractice" in baseline_word_stats and
                        activity_type in baseline_word_stats["directPractice"]):
                        baseline_activity = baseline_word_stats["directPractice"][activity_type]
                        baseline_correct = baseline_activity.get("correct", 0)
                        baseline_incorrect = baseline_activity.get("incorrect", 0)

                    # Calculate delta
                    progress["directPractice"][activity_type]["correct"] += max(0, current_correct - baseline_correct)
                    progress["directPractice"][activity_type]["incorrect"] += max(0, current_incorrect - baseline_incorrect)

        # Calculate contextualExposure deltas
        if "contextualExposure" in current_word_stats:
            for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
                if activity_type in current_word_stats["contextualExposure"]:
                    current_activity = current_word_stats["contextualExposure"][activity_type]
                    current_correct = current_activity.get("correct", 0)
                    current_incorrect = current_activity.get("incorrect", 0)

                    baseline_correct = 0
                    baseline_incorrect = 0
                    if (baseline_word_stats and "contextualExposure" in baseline_word_stats and
                        activity_type in baseline_word_stats["contextualExposure"]):
                        baseline_activity = baseline_word_stats["contextualExposure"][activity_type]
                        baseline_correct = baseline_activity.get("correct", 0)
                        baseline_incorrect = baseline_activity.get("incorrect", 0)

                    progress["contextualExposure"][activity_type]["correct"] += max(0, current_correct - baseline_correct)
                    progress["contextualExposure"][activity_type]["incorrect"] += max(0, current_incorrect - baseline_incorrect)

    return progress


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
        raise ValueError(f"Invalid stat type format: {stat_type}. Expected format: 'category.activity'")

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
        raise ValueError(f"Invalid category: {category}. Must be 'directPractice' or 'contextualExposure'")

    return category, activity, is_contextual


def increment_word_stat(
    journey_stats: "JourneyStats",
    word_key: str,
    category: str,
    activity: str,
    correct: bool,
    is_contextual: bool,
    current_timestamp: int
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
    if "directPractice" not in word_stats or "contextualExposure" not in word_stats or "practiceHistory" not in word_stats:
        # Migrate to new schema if needed
        word_stats = validate_and_normalize_word_stats(word_stats)
        journey_stats.stats["stats"][word_key] = word_stats

    # Increment the appropriate counter
    if category not in word_stats:
        if category == "directPractice":
            word_stats[category] = {act: {"correct": 0, "incorrect": 0} for act in DIRECT_PRACTICE_TYPES}
        else:
            word_stats[category] = {act: {"correct": 0, "incorrect": 0} for act in CONTEXTUAL_EXPOSURE_TYPES}

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
            "lastIncorrectAnswer": None
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


class BaseStats:
    """Base class for stats management with common functionality."""

    def __init__(self, user_id: str, language: str = "lithuanian"):
        self.user_id = str(user_id)
        self.language = language
        self._stats = None
        self._loaded = False
    
    @property
    def file_path(self) -> str:
        """Get the file path for this stats file. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load stats from the specified file path."""
        if not os.path.exists(file_path):
            logger.debug(f"No stats file found at {file_path}, returning empty stats")
            return {"stats": {}}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data if isinstance(data, dict) and "stats" in data else {"stats": {}}
    
    def _save_to_file(self, file_path: str, stats: Dict[str, Any]) -> bool:
        """Save stats to the specified file path."""
        try:
            ensure_user_data_dir(self.user_id)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Error saving stats to {file_path}: {str(e)}")
            return False
    
    def load(self) -> bool:
        """Load the stats from the file."""
        try:
            self._stats = self._load_from_file(self.file_path)
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading stats for user {self.user_id}: {str(e)}")
            self._stats = {"stats": {}}
            self._loaded = True
            return False
    
    def save(self) -> bool:
        """Save the current stats to the file."""
        if not self._loaded or self._stats is None:
            logger.warning(f"Attempting to save unloaded stats for user {self.user_id}")
            return False
        return self._save_to_file(self.file_path, self._stats)
    
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
    
    def get_word_stats(self, word_key: str) -> Dict[str, Any]:
        """Get stats for a specific word."""
        return self.stats["stats"].get(word_key, {})
    
    def set_word_stats(self, word_key: str, word_stats: Dict[str, Any]):
        """Set stats for a specific word."""
        if not self._loaded:
            self.load()
        if "stats" not in self._stats:
            self._stats["stats"] = {}
        self._stats["stats"][word_key] = word_stats
    
    def is_empty(self) -> bool:
        """Check if the stats are empty (no word stats)."""
        return not bool(self.stats["stats"])


class JourneyStats(BaseStats):
    """Manages access to a user's main journey stats file."""

    @property
    def file_path(self) -> str:
        """Get the file path for this user's journey stats file."""
        user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", self.user_id, self.language)
        os.makedirs(user_data_dir, exist_ok=True)
        return os.path.join(user_data_dir, "stats.json")
    
    def load(self) -> bool:
        """Load the stats from the file with filtering."""
        try:
            data = self._load_from_file(self.file_path)
            
            # Filter out invalid stat types
            filtered_stats = {}
            if "stats" in data:
                for word_key, word_stats in data["stats"].items():
                    filtered_stats[word_key] = validate_and_normalize_word_stats(word_stats)
            
            self._stats = {"stats": filtered_stats}
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading journey stats for user {self.user_id}: {str(e)}")
            self._stats = {"stats": {}}
            self._loaded = True
            return False
    
    def save(self) -> bool:
        """Save the current stats to the file with filtering."""
        if not self._loaded or self._stats is None:
            logger.warning(f"Attempting to save unloaded journey stats for user {self.user_id}")
            return False
        
        # Filter out invalid stat types before saving
        filtered_data = {"stats": {}}
        if "stats" in self._stats:
            for word_key, word_stats in self._stats["stats"].items():
                filtered_data["stats"][word_key] = validate_and_normalize_word_stats(word_stats)
        
        return self._save_to_file(self.file_path, filtered_data)
    
    def set_word_stats(self, word_key: str, word_stats: Dict[str, Any]):
        """Set stats for a specific word (with filtering)."""
        super().set_word_stats(word_key, validate_and_normalize_word_stats(word_stats))
    
    def save_with_daily_update(self) -> bool:
        """Save journey stats and update daily snapshots."""
        try:
            if not ensure_daily_snapshots(self.user_id, self.language):
                logger.warning(f"Failed to ensure daily snapshots for user {self.user_id} language {self.language}")

            if not self.save():
                return False

            # Update current daily snapshot
            current_day = get_current_day_key()
            current_daily_stats = DailyStats(self.user_id, current_day, "current", self.language)
            current_daily_stats.stats = self._stats
            if not current_daily_stats.save():
                logger.warning(f"Failed to update current daily snapshot for user {self.user_id}")

            return True
        except Exception as e:
            logger.error(f"Error saving journey stats with daily update for user {self.user_id}: {str(e)}")
            return False


class DailyStats(BaseStats):
    """Manages access to a single daily stats file for a specific user and date."""

    def __init__(self, user_id: str, date: str, stats_type: str = "current", language: str = "lithuanian"):
        super().__init__(user_id, language)
        self.date = date
        self.stats_type = stats_type
        self._loaded_from_gzip = False

    @property
    def file_path(self) -> str:
        """Get the file path for this daily stats file."""
        daily_dir = os.path.join(constants.DATA_DIR, "trakaido", self.user_id, self.language, "daily")
        os.makedirs(daily_dir, exist_ok=True)
        return os.path.join(daily_dir, f"{self.date}_{self.stats_type}.json")

    @property
    def gzip_file_path(self) -> str:
        """Get the GZIP file path for this daily stats file."""
        daily_dir = os.path.join(constants.DATA_DIR, "trakaido", self.user_id, self.language, "daily")
        os.makedirs(daily_dir, exist_ok=True)
        return os.path.join(daily_dir, f"{self.date}_{self.stats_type}.json.gz")
    
    @property
    def is_gzip_loaded(self) -> bool:
        """Check if this instance was loaded from a GZIP file."""
        return self._loaded_from_gzip
    
    def _load_from_gzip(self, file_path: str) -> Dict[str, Any]:
        """Load stats from a GZIP file."""
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) and "stats" in data else {"stats": {}}
        except Exception as e:
            logger.error(f"Error loading GZIP stats from {file_path}: {str(e)}")
            return {"stats": {}}
    
    def load(self) -> bool:
        """Load the stats from the file, checking GZIP first."""
        try:
            # Check for GZIP file first
            if os.path.exists(self.gzip_file_path):
                self._stats = self._load_from_gzip(self.gzip_file_path)
                self._loaded = True
                self._loaded_from_gzip = True
                return True
            
            # Fall back to regular JSON file
            if os.path.exists(self.file_path):
                self._stats = self._load_from_file(self.file_path)
                self._loaded = True
                self._loaded_from_gzip = False
                return True
            
            # No file found
            logger.debug(f"No stats file found for {self.date}_{self.stats_type}, returning empty stats")
            self._stats = {"stats": {}}
            self._loaded = True
            self._loaded_from_gzip = False
            return False
        except Exception as e:
            logger.error(f"Error loading daily stats for user {self.user_id} date {self.date}: {str(e)}")
            self._stats = {"stats": {}}
            self._loaded = True
            self._loaded_from_gzip = False
            return False
    
    def save(self) -> bool:
        """Save the current stats to the file. GZIP files cannot be modified once written."""
        if not self._loaded or self._stats is None:
            logger.warning(f"Attempting to save unloaded daily stats for user {self.user_id}")
            return False
        
        # Check if this was loaded from GZIP - if so, we cannot modify it
        if self._loaded_from_gzip:
            logger.warning(f"Cannot save daily stats for user {self.user_id} date {self.date} - loaded from GZIP file (read-only)")
            return False
        
        # Save to regular JSON file
        return self._save_to_file(self.file_path, self._stats)
    
    @classmethod
    def exists(cls, user_id: str, date: str, stats_type: str = "current", language: str = "lithuanian") -> bool:
        """Check if a daily stats file exists (either regular or GZIP)."""
        temp_instance = cls(user_id, date, stats_type, language)
        return os.path.exists(temp_instance.gzip_file_path) or os.path.exists(temp_instance.file_path)
    
    @staticmethod
    def get_available_dates(user_id: str, stats_type: str = "current", language: str = "lithuanian") -> List[str]:
        """Get all available dates for a user's daily stats files (including GZIP)."""
        try:
            daily_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language, "daily")
            if not os.path.exists(daily_dir):
                return []

            dates = set()
            json_suffix = f"_{stats_type}.json"
            gzip_suffix = f"_{stats_type}.json.gz"

            for filename in os.listdir(daily_dir):
                date_part = None

                # Check for regular JSON files
                if filename.endswith(json_suffix):
                    date_part = filename[:-len(json_suffix)]
                # Check for GZIP files
                elif filename.endswith(gzip_suffix):
                    date_part = filename[:-len(gzip_suffix)]

                if date_part and len(date_part) == 10 and date_part.count('-') == 2:
                    dates.add(date_part)

            return sorted(list(dates))
        except Exception as e:
            logger.error(f"Error getting available dates for user {user_id}: {str(e)}")
            return []
    
    def get_stat_type_total(self, stat_type: str) -> Dict[str, int]:
        """Get total correct/incorrect counts for a specific stat type across all words.

        For new schema, stat_type should be in format: "directPractice.multipleChoice_englishToTarget"
        or "contextualExposure.sentences"
        """
        totals = {"correct": 0, "incorrect": 0}

        # Handle new nested schema
        if "." in stat_type:
            category, activity = stat_type.split(".", 1)
            for word_stats in self.stats["stats"].values():
                if category in word_stats and isinstance(word_stats[category], dict):
                    if activity in word_stats[category] and isinstance(word_stats[category][activity], dict):
                        totals["correct"] += word_stats[category][activity].get("correct", 0)
                        totals["incorrect"] += word_stats[category][activity].get("incorrect", 0)
        else:
            # Legacy support for old flat stat types
            for word_stats in self.stats["stats"].values():
                if stat_type in word_stats and isinstance(word_stats[stat_type], dict):
                    totals["correct"] += word_stats[stat_type].get("correct", 0)
                    totals["incorrect"] += word_stats[stat_type].get("incorrect", 0)

        return totals

    def get_all_stat_totals(self) -> Dict[str, Dict[str, int]]:
        """Get total correct/incorrect counts for all stat types."""
        totals = {}

        # Get totals for all direct practice activities
        for activity_type in DIRECT_PRACTICE_TYPES:
            key = f"directPractice.{activity_type}"
            totals[key] = self.get_stat_type_total(key)

        # Get totals for contextual exposure
        for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
            key = f"contextualExposure.{activity_type}"
            totals[key] = self.get_stat_type_total(key)

        return totals
    
    def compress_to_gzip(self) -> bool:
        """Compress the regular JSON file to GZIP and remove the original."""
        try:
            # Check if regular file exists
            if not os.path.exists(self.file_path):
                logger.debug(f"No regular file to compress at {self.file_path}")
                return False
            
            # Check if GZIP file already exists
            if os.path.exists(self.gzip_file_path):
                logger.warning(f"GZIP file already exists at {self.gzip_file_path}")
                return False
            
            # Read the regular file and write to GZIP
            with open(self.file_path, 'r', encoding='utf-8') as f_in:
                with gzip.open(self.gzip_file_path, 'wt', encoding='utf-8') as f_out:
                    f_out.write(f_in.read())
            
            # Remove the original file
            os.remove(self.file_path)
            
            logger.debug(f"Successfully compressed {self.file_path} to {self.gzip_file_path}")
            return True
        except Exception as e:
            logger.error(f"Error compressing file {self.file_path} to GZIP: {str(e)}")
            return False


# Daily Stats Functions
def compress_previous_day_files(user_id: str, language: str = "lithuanian") -> bool:
    """Compress previous day files to GZIP during daily rotation."""
    try:
        current_day = get_current_day_key()
        current_date = datetime.strptime(current_day, "%Y-%m-%d")

        # Get all available dates for this user and language
        available_dates = DailyStats.get_available_dates(user_id, "current", language)
        available_dates.extend(DailyStats.get_available_dates(user_id, "yesterday", language))
        available_dates = list(set(available_dates))  # Remove duplicates

        compressed_count = 0

        for date_str in available_dates:
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Only compress files from previous days (not current day)
                if file_date < current_date:
                    for stats_type in ["current", "yesterday"]:
                        daily_stats = DailyStats(user_id, date_str, stats_type, language)

                        # Only compress if regular file exists and GZIP doesn't
                        if (os.path.exists(daily_stats.file_path) and
                            not os.path.exists(daily_stats.gzip_file_path)):

                            if daily_stats.compress_to_gzip():
                                compressed_count += 1
                                logger.debug(f"Compressed {date_str}_{stats_type}.json for user {user_id} language {language}")

            except ValueError:
                # Skip invalid date formats
                continue

        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} previous day files for user {user_id} language {language}")

        return True
    except Exception as e:
        logger.error(f"Error compressing previous day files for user {user_id} language {language}: {str(e)}")
        return False


def ensure_daily_snapshots(user_id: str, language: str = "lithuanian") -> bool:
    """Ensure that daily snapshots are properly set up for the current day."""
    try:
        current_day = get_current_day_key()

        # Check if we need to create yesterday's snapshot
        yesterday_daily_stats = DailyStats(user_id, current_day, "yesterday", language)
        if not DailyStats.exists(user_id, current_day, "yesterday", language) or yesterday_daily_stats.is_empty():
            journey_stats = JourneyStats(user_id, language)
            yesterday_daily_stats.stats = journey_stats.stats
            yesterday_daily_stats.save()
            logger.debug(f"Created yesterday snapshot for user {user_id} day {current_day} language {language}")

        # Ensure current snapshot exists
        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        if not DailyStats.exists(user_id, current_day, "current", language):
            journey_stats = JourneyStats(user_id, language)
            current_daily_stats.stats = journey_stats.stats
            current_daily_stats.save()
            logger.debug(f"Created current snapshot for user {user_id} day {current_day} language {language}")

        # Compress previous day files once current day is set up
        compress_previous_day_files(user_id, language)

        # Clean up old nonce files (keep only today and yesterday)
        cleanup_old_nonce_files(user_id, language)

        return True
    except Exception as e:
        logger.error(f"Error ensuring daily snapshots for user {user_id} language {language}: {str(e)}")
        return False


def calculate_daily_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate daily progress by comparing current and yesterday snapshots."""
    try:
        current_day = get_current_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        yesterday_daily_stats = DailyStats(user_id, current_day, "yesterday", language)
        current_daily_stats = DailyStats(user_id, current_day, "current", language)

        # Calculate progress delta
        daily_progress = calculate_progress_delta(current_daily_stats, yesterday_daily_stats)

        return {"currentDay": current_day, "progress": daily_progress}
    except Exception as e:
        logger.error(f"Error calculating daily progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


def find_best_baseline(user_id: str, target_day: str, max_days: int, language: str = "lithuanian") -> DailyStats:
    """Find the best available baseline stats for comparison over a given period.
    
    Args:
        user_id: The user ID to find baseline stats for
        target_day: The target day to find baseline stats for (YYYY-MM-DD format)
        max_days: Maximum number of days to look forward from target day
    
    Returns:
        DailyStats object with the best available baseline stats
    """
    try:
        # Try exact target day first
        target_daily_stats = DailyStats(user_id, target_day, "current", language)
        if DailyStats.exists(user_id, target_day, "current", language) and not target_daily_stats.is_empty():
            return target_daily_stats

        # If target date doesn't exist, walk forward and find the oldest "yesterday" snapshot
        # that is less than max_days old from the target date
        target_date = datetime.strptime(target_day, "%Y-%m-%d")
        yesterday_dates = DailyStats.get_available_dates(user_id, "yesterday", language)

        best_daily_stats = None
        best_date = None

        # Check up to max_days forward from target
        for days_forward in range(1, max_days + 1):
            check_date = target_date + timedelta(days=days_forward)
            check_day_key = check_date.strftime("%Y-%m-%d")

            if check_day_key in yesterday_dates:
                check_daily_stats = DailyStats(user_id, check_day_key, "yesterday", language)
                if not check_daily_stats.is_empty():
                    # We want the oldest (earliest) "yesterday" snapshot, so take the first one we find
                    if best_date is None or check_date < best_date:
                        best_daily_stats = check_daily_stats
                        best_date = check_date

        if best_daily_stats:
            return best_daily_stats
        else:
            period_name = "weekly" if max_days <= 7 else "monthly"
            logger.debug(f"No suitable {period_name} baseline found for user {user_id} language {language}, using empty baseline")
            empty_stats = DailyStats(user_id, target_day, "current", language)
            empty_stats.stats = {"stats": {}}
            return empty_stats

    except Exception as e:
        period_name = "weekly" if max_days <= 7 else "monthly"
        logger.error(f"Error finding {period_name} baseline for user {user_id} language {language}: {str(e)}")
        empty_stats = DailyStats(user_id, target_day, "current", language)
        empty_stats.stats = {"stats": {}}
        return empty_stats


def calculate_weekly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate weekly progress by comparing current stats with stats from 7 days ago."""
    try:
        current_day = get_current_day_key()
        week_ago_day = get_week_ago_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        week_ago_daily_stats = find_best_baseline(user_id, week_ago_day, 7, language)

        # Calculate progress delta
        weekly_progress = calculate_progress_delta(current_daily_stats, week_ago_daily_stats)

        actual_baseline_day = week_ago_daily_stats.date if not week_ago_daily_stats.is_empty() else None

        return {
            "currentDay": current_day,
            "targetBaselineDay": week_ago_day,
            "actualBaselineDay": actual_baseline_day,
            "progress": weekly_progress
        }
    except Exception as e:
        logger.error(f"Error calculating weekly progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


def calculate_monthly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """
    Calculate monthly stats with daily breakdown and monthly aggregate for the past 30 days.

    Returns two main components:
    1. monthlyAggregate - Aggregate stats for the entire 30-day period (similar to weekly stats)
    2. dailyData - Per-day stats showing:
       - questionsAnswered: Number of questions answered on each day
       - exposedWordsCount: Total number of exposed words on each day
       - newlyExposedWords: Number of words newly exposed on each day (compared to most recent previous day with data)
    """
    try:
        current_day = get_current_day_key()
        thirty_days_ago_day = get_30_days_ago_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        # Get current stats and baseline for summary
        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        thirty_days_ago_daily_stats = find_best_baseline(user_id, thirty_days_ago_day, 30, language)

        # Calculate monthly aggregate stats using delta helper
        monthly_aggregate = calculate_progress_delta(current_daily_stats, thirty_days_ago_daily_stats)
        
        # Get daily breakdown for the past 30 days
        start_date_str, end_date_str = get_30_day_date_range()
        available_dates = DailyStats.get_available_dates(user_id, "current", language)
        
        daily_data = []
        
        # Generate all dates in the past 30 days
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            questions_answered_on_day = 0
            exposed_words_count_on_day = 0
            newly_exposed_words_on_day = 0
            
            if date_str in available_dates:
                daily_stats = DailyStats(user_id, date_str, "current", language)
                if not daily_stats.is_empty():
                    # Calculate questions answered on this day (sum of all correct + incorrect for all stat types)
                    for word_key, word_stats in daily_stats.stats["stats"].items():
                        # Count directPractice activities
                        if "directPractice" in word_stats:
                            for activity_type in DIRECT_PRACTICE_TYPES:
                                if activity_type in word_stats["directPractice"]:
                                    activity_stats = word_stats["directPractice"][activity_type]
                                    if isinstance(activity_stats, dict):
                                        questions_answered_on_day += activity_stats.get("correct", 0)
                                        questions_answered_on_day += activity_stats.get("incorrect", 0)
                        # Count contextualExposure activities
                        if "contextualExposure" in word_stats:
                            for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
                                if activity_type in word_stats["contextualExposure"]:
                                    activity_stats = word_stats["contextualExposure"][activity_type]
                                    if isinstance(activity_stats, dict):
                                        questions_answered_on_day += activity_stats.get("correct", 0)
                                        questions_answered_on_day += activity_stats.get("incorrect", 0)
                    
                    # Count exposed words on this day
                    for word_key, word_stats in daily_stats.stats["stats"].items():
                        if word_stats.get("exposed", False):
                            exposed_words_count_on_day += 1
                    
                    # Calculate new exposed words on this day by finding the most recent previous data
                    if current_date > start_date:
                        # Find the most recent previous day with data
                        most_recent_prev_date = None
                        most_recent_prev_stats = None
                        
                        # Start from yesterday and go backwards until we find data
                        check_date = current_date - timedelta(days=1)
                        while check_date >= start_date:
                            check_date_str = check_date.strftime("%Y-%m-%d")
                            if check_date_str in available_dates:
                                prev_daily_stats = DailyStats(user_id, check_date_str, "current", language)
                                if not prev_daily_stats.is_empty():
                                    most_recent_prev_date = check_date_str
                                    most_recent_prev_stats = prev_daily_stats
                                    break
                            check_date -= timedelta(days=1)
                        
                        if most_recent_prev_stats:
                            # Count words that are exposed today but weren't exposed in the most recent previous day with data
                            for word_key, word_stats in daily_stats.stats["stats"].items():
                                if word_stats.get("exposed", False):
                                    prev_word_stats = most_recent_prev_stats.get_word_stats(word_key)
                                    if not prev_word_stats or not prev_word_stats.get("exposed", False):
                                        newly_exposed_words_on_day += 1
                        else:
                            # If no previous data within the period, try to find data from before the period
                            baseline_found = False
                            all_available_dates = DailyStats.get_available_dates(user_id, "current", language)
                            earlier_dates = [d for d in all_available_dates if datetime.strptime(d, "%Y-%m-%d") < start_date]

                            if earlier_dates:
                                # Use the most recent date before our period as baseline
                                baseline_date = max(earlier_dates)
                                baseline_stats = DailyStats(user_id, baseline_date, "current", language)
                                
                                if not baseline_stats.is_empty():
                                    baseline_found = True
                                    # Count words that are exposed on this day but weren't in baseline
                                    for word_key, word_stats in daily_stats.stats["stats"].items():
                                        if word_stats.get("exposed", False):
                                            baseline_word_stats = baseline_stats.get_word_stats(word_key)
                                            if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                                                newly_exposed_words_on_day += 1
                            
                            # If no valid baseline found, set newly exposed to 0 since we can't determine what's new
                            if not baseline_found:
                                newly_exposed_words_on_day = 0
                    else:
                        # First day of the 30-day period with data
                        # Try to find a baseline from before the 30-day period to compare with
                        baseline_found = False

                        # Look for snapshots before the start date
                        all_available_dates = DailyStats.get_available_dates(user_id, "current", language)
                        earlier_dates = [d for d in all_available_dates if datetime.strptime(d, "%Y-%m-%d") < start_date]

                        if earlier_dates:
                            # Use the most recent date before our period as baseline
                            baseline_date = max(earlier_dates)
                            baseline_stats = DailyStats(user_id, baseline_date, "current", language)
                            
                            if not baseline_stats.is_empty():
                                baseline_found = True
                                # Count words that are exposed on first day but weren't in baseline
                                for word_key, word_stats in daily_stats.stats["stats"].items():
                                    if word_stats.get("exposed", False):
                                        baseline_word_stats = baseline_stats.get_word_stats(word_key)
                                        if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                                            newly_exposed_words_on_day += 1
                        
                        # If no valid baseline found, set newly exposed to 0 since we can't determine what's new
                        if not baseline_found:
                            newly_exposed_words_on_day = 0
            
            daily_data.append({
                "date": date_str,
                "questionsAnswered": questions_answered_on_day,
                "exposedWordsCount": exposed_words_count_on_day,
                "newlyExposedWords": newly_exposed_words_on_day
            })
            
            current_date += timedelta(days=1)
        
        actual_baseline_day = thirty_days_ago_daily_stats.date if not thirty_days_ago_daily_stats.is_empty() else None
        
        # Format the period description
        period_description = f"Past 30 Days ({start_date_str} to {end_date_str})"
        
        return {
            "currentMonth": period_description,
            "currentDay": current_day,
            "targetBaselineDay": thirty_days_ago_day,
            "actualBaselineDay": actual_baseline_day,
            "monthlyAggregate": monthly_aggregate,
            "dailyData": daily_data
        }
    except Exception as e:
        logger.error(f"Error calculating monthly progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


# Journey Stats API Routes
@trakaido_bp.route('/api/trakaido/journeystats/', methods=['GET'])
@require_auth
def get_all_journey_stats():
    """Get all journey stats for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        journey_stats = JourneyStats(user_id, language)
        return jsonify(journey_stats.stats)
    except Exception as e:
        logger.error(f"Error getting all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/', methods=['PUT'])
@require_auth
def save_all_journey_stats():
    """Save all journey stats for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "stats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'stats' field."}), 400

        journey_stats = JourneyStats(user_id, language)
        journey_stats.stats = data
        if journey_stats.save_with_daily_update():
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to save journey stats"}), 500
    except Exception as e:
        logger.error(f"Error saving all journey stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/word', methods=['POST'])
@require_auth
def update_word_stats():
    """Update stats for a specific word for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        data = request.get_json()

        if not data or "wordKey" not in data or "wordStats" not in data:
            return jsonify({"error": "Invalid request body. Expected 'wordKey' and 'wordStats' fields."}), 400

        word_key = data["wordKey"]
        word_stats = data["wordStats"]

        journey_stats = JourneyStats(user_id, language)
        journey_stats.set_word_stats(word_key, word_stats)
        
        if journey_stats.save_with_daily_update():
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update word stats"}), 500
    except Exception as e:
        logger.error(f"Error updating word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/word/<word_key>', methods=['GET'])
@require_auth
def get_word_stats(word_key: str):
    """Get stats for a specific word for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        journey_stats = JourneyStats(user_id, language)
        word_stats = journey_stats.get_word_stats(word_key)
        return jsonify({"wordStats": word_stats})
    except Exception as e:
        logger.error(f"Error getting word stats for '{word_key}': {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/increment', methods=['POST'])
@require_auth
def increment_word_stats():
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

        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        current_day = get_current_day_key()

        # Check if nonce has already been used (today or yesterday)
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({"error": "Nonce already used"}), 409

        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id, language):
            return jsonify({"error": "Failed to initialize daily stats"}), 500

        # Load current overall stats
        journey_stats = JourneyStats(user_id, language)

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
            logger.warning(f"Failed to save nonce for user {user_id} day {current_day} language {language}")

        return jsonify({
            "success": True,
            "wordKey": word_key,
            "statType": stat_type,
            "correct": correct,
            "newStats": word_stats[category][activity]
        })
        
    except Exception as e:
        logger.error(f"Error incrementing word stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/bulk_increment', methods=['POST'])
@require_auth
def bulk_increment_word_stats():
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
            return jsonify({"error": "Invalid request body. Expected 'nonce' and 'increments' fields."}), 400

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

        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        current_day = get_current_day_key()

        # Check if this batch nonce has already been used
        if check_nonce_duplicates(user_id, nonce, language):
            return jsonify({"error": "Batch nonce already used"}), 409

        # Ensure daily snapshots exist
        if not ensure_daily_snapshots(user_id, language):
            return jsonify({"error": "Failed to initialize daily stats"}), 500

        # Load journey stats once
        journey_stats = JourneyStats(user_id, language)

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
                    results.append({
                        "index": idx,
                        "status": "failed",
                        "reason": f"Missing fields: {', '.join(missing_fields)}"
                    })
                    continue

                word_key = increment["wordKey"]
                stat_type = increment["statType"]
                correct = increment["correct"]

                # Validate correct field
                if not isinstance(correct, bool):
                    failed_count += 1
                    results.append({
                        "index": idx,
                        "status": "failed",
                        "reason": "'correct' must be a boolean"
                    })
                    continue

                # Parse stat type using helper function
                try:
                    category, activity, is_contextual = parse_stat_type(stat_type)
                except ValueError as e:
                    failed_count += 1
                    results.append({
                        "index": idx,
                        "status": "failed",
                        "reason": str(e)
                    })
                    continue

                # Increment the word stats using helper function
                increment_word_stat(
                    journey_stats, word_key, category, activity, correct, is_contextual, current_timestamp
                )

                processed_count += 1
                results.append({
                    "index": idx,
                    "status": "success"
                })

            except Exception as e:
                failed_count += 1
                results.append({
                    "index": idx,
                    "status": "failed",
                    "reason": str(e)
                })
                logger.error(f"Error processing increment {idx}: {str(e)}")

        # Save updated stats if any were processed
        if processed_count > 0:
            if not journey_stats.save_with_daily_update():
                return jsonify({"error": "Failed to save stats after processing"}), 500

            # Save the batch nonce
            language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
            used_nonces = load_nonces(user_id, current_day, language)
            used_nonces.add(nonce)
            if not save_nonces(user_id, current_day, used_nonces, language):
                logger.warning(f"Failed to save nonce for user {user_id} day {current_day} language {language}")

        return jsonify({
            "success": True,
            "processed": processed_count,
            "failed": failed_count,
            "results": results
        })

    except Exception as e:
        logger.error(f"Error in bulk increment: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/daily', methods=['GET'])
@require_auth
def get_daily_stats():
    """Get daily stats (today's progress) for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        daily_progress = calculate_daily_progress(user_id, language)

        if "error" in daily_progress:
            return jsonify(daily_progress), 500

        return jsonify(daily_progress)
    except Exception as e:
        logger.error(f"Error getting daily stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/weekly', methods=['GET'])
@require_auth
def get_weekly_stats():
    """Get weekly stats (7-day progress) for the authenticated user."""
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        weekly_progress = calculate_weekly_progress(user_id, language)

        if "error" in weekly_progress:
            return jsonify(weekly_progress), 500

        return jsonify(weekly_progress)
    except Exception as e:
        logger.error(f"Error getting weekly stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/journeystats/monthly', methods=['GET'])
@require_auth
def get_monthly_stats():
    """
    Get monthly stats for the authenticated user.

    Returns:
    - monthlyAggregate: Aggregate stats for the entire 30-day period
    - dailyData: Per-day stats showing questions answered, exposed words count, and newly exposed words
    """
    try:
        user_id = str(g.user.id)
        language = g.current_language if hasattr(g, 'current_language') else "lithuanian"
        monthly_progress = calculate_monthly_progress(user_id, language)

        if "error" in monthly_progress:
            return jsonify(monthly_progress), 500

        return jsonify(monthly_progress)
    except Exception as e:
        logger.error(f"Error getting monthly stats: {str(e)}")
        return jsonify({"error": str(e)}), 500