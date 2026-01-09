"""Stats schema definitions, validation, and storage classes for Trakaido user statistics."""

# Standard library imports
import gzip
import json
import os
from typing import Any, Dict, List

# Local application imports
import constants
from .shared import logger, ensure_user_data_dir


##############################################################################
# Activity Stats Schema Constants
##############################################################################

# Direct practice activities (count toward proficiency)
DIRECT_PRACTICE_TYPES = {
    "multipleChoice_englishToTarget",
    "multipleChoice_targetToEnglish",
    "listening_targetAudioToTarget",
    "listening_targetAudioToEnglish",
    "typing_englishToTarget",
    "typing_targetToEnglish",
    "spelling_englishToTarget",
    "blitz_englishToTarget",
    "blitz_targetToEnglish",
    "sentenceCompletion_targetCloze",
}

# Contextual exposure activities (don't count toward proficiency)
CONTEXTUAL_EXPOSURE_TYPES = {"sentences", "flashcards", "categoryChoice"}

# All valid stat types
ALL_STAT_TYPES = DIRECT_PRACTICE_TYPES | CONTEXTUAL_EXPOSURE_TYPES

# Top-level fields
TOP_LEVEL_FIELDS = {"exposed", "markedAsKnown", "directPractice", "contextualExposure", "practiceHistory"}


##############################################################################
# Schema Creation and Validation
##############################################################################

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
# JSON Formatting Helper
##############################################################################

def format_stats_json(stats: Dict[str, Any]) -> str:
    """Format stats JSON with each word entry on one line.

    Creates a more compact format where:
    - Top level structure has line breaks
    - Each word key's entire value is on one line

    Example:
    {
      "stats": {
        "N08_011": {"exposed": true, "directPractice": {...}, ...},
        "N08_012": {"exposed": true, "directPractice": {...}, ...}
      }
    }
    """
    if not stats or "stats" not in stats:
        return json.dumps(stats, ensure_ascii=False)

    lines = ['{']
    lines.append('  "stats": {')

    word_items = list(stats["stats"].items())
    for i, (word_key, word_stats) in enumerate(word_items):
        # Serialize the entire word stats dict on one line
        word_json = json.dumps(word_stats, ensure_ascii=False, separators=(',', ': '))
        comma = ',' if i < len(word_items) - 1 else ''
        lines.append(f'    "{word_key}": {word_json}{comma}')

    lines.append('  }')
    lines.append('}')

    return '\n'.join(lines)


##############################################################################
# Base Storage Classes
##############################################################################

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

            # Format the JSON once for both size check and saving
            formatted_json = format_stats_json(stats)

            # Check for suspicious large size reductions (>90% smaller)
            if os.path.exists(file_path):
                try:
                    old_size = os.path.getsize(file_path)
                    new_size = len(formatted_json.encode('utf-8'))

                    # If new size is more than 90% smaller, reject the update
                    if old_size > 10000 and new_size < (old_size * 0.1):
                        logger.error(
                            f"REJECTED: Suspicious stats update for user {self.user_id} "
                            f"at {file_path}. Size dropped from {old_size} bytes to {new_size} bytes "
                            f"(reduction: {((old_size - new_size) / old_size * 100):.1f}%). "
                            f"This looks like a data loss bug. Update blocked."
                        )
                        # Return True to send fake "success" to client
                        return True
                except Exception as e:
                    logger.warning(f"Error checking file size for {file_path}: {str(e)}")
                    # Continue with save if size check fails

            # Save with custom formatting (each word entry on one line)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_json)

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
        # Import here to avoid circular dependency
        from .stats_snapshots import ensure_daily_snapshots
        from .date_utils import get_current_day_key

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
