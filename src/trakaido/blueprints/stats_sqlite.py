"""SQLite storage backend for Trakaido word statistics.

This module provides a SQLite-based alternative to the flat file storage
for word learning statistics. Each user gets their own SQLite database.

Design decisions:
- One database per user per language (stored alongside existing flat files)
- Word stats stored in normalized tables for efficient querying
- Daily snapshots stored as aggregate summaries (not full per-word copies)
- Nonces kept in flat files (shared with grammar stats)
- Backend selection via server_settings.json in user data directory

Migration script: tools/migrate_flatfile_to_sqlite.py
"""

# Standard library imports
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Local application imports
import constants
from trakaido.blueprints.shared import logger
from trakaido.blueprints.stats_schema import (
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
    create_empty_word_stats,
    validate_and_normalize_word_stats,
)
from trakaido.blueprints.stats_metrics import (
    build_activity_summary_from_totals,
    empty_activity_summary,
)
from trakaido.blueprints.date_utils import (
    get_current_day_key,
    get_yesterday_day_key,
    get_week_ago_day_key,
    get_30_days_ago_day_key,
    get_30_day_date_range,
)

SCHEMA_VERSION = 1


def _get_db_path(user_id: str, language: str = "lithuanian") -> str:
    """Get the path to the user's SQLite database file."""
    user_data_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language)
    os.makedirs(user_data_dir, exist_ok=True)
    return os.path.join(user_data_dir, "stats.db")


class SqliteStatsDB:
    """Low-level SQLite database operations for word statistics.

    Manages a per-user SQLite database with tables for:
    - word_stats: Current state of each word (exposed, timestamps)
    - word_activity_stats: Correct/incorrect counts per word per activity
    - daily_snapshots: End-of-day aggregate data for progress calculations
    - schema_info: Database metadata and version tracking
    """

    def __init__(self, user_id: str, language: str = "lithuanian"):
        self.user_id = str(user_id)
        self.language = language
        self.db_path = _get_db_path(user_id, language)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS word_stats (
                    word_key TEXT PRIMARY KEY,
                    exposed INTEGER NOT NULL DEFAULT 0,
                    marked_as_known INTEGER NOT NULL DEFAULT 0,
                    last_seen INTEGER,
                    last_correct_answer INTEGER,
                    last_incorrect_answer INTEGER
                );

                CREATE TABLE IF NOT EXISTS word_activity_stats (
                    word_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    correct INTEGER NOT NULL DEFAULT 0,
                    incorrect INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (word_key, category, activity),
                    FOREIGN KEY (word_key) REFERENCES word_stats(word_key)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS daily_snapshots (
                    date TEXT PRIMARY KEY,
                    exposed_words_count INTEGER NOT NULL DEFAULT 0,
                    words_known_count INTEGER NOT NULL DEFAULT 0,
                    total_questions_answered INTEGER NOT NULL DEFAULT 0,
                    newly_exposed_words INTEGER NOT NULL DEFAULT 0,
                    activity_totals_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS schema_info (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """
            )

            # Forward-compatible migration: older DBs may not have
            # words_known_count in daily_snapshots.
            snapshot_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(daily_snapshots)")
            }
            if "words_known_count" not in snapshot_columns:
                conn.execute(
                    "ALTER TABLE daily_snapshots ADD COLUMN words_known_count INTEGER NOT NULL DEFAULT 0"
                )

            cursor = conn.execute("SELECT value FROM schema_info WHERE key = 'version'")
            row = cursor.fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO schema_info (key, value) VALUES ('version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif row["value"] != str(SCHEMA_VERSION):
                conn.execute(
                    "UPDATE schema_info SET value = ? WHERE key = 'version'",
                    (str(SCHEMA_VERSION),),
                )

            conn.commit()
        finally:
            conn.close()

    ##########################################################################
    # Word Stats CRUD
    ##########################################################################

    def get_all_stats(self) -> Dict[str, Any]:
        """Load all word stats in the standard dict format.

        Returns:
            Dict matching the flat file format: {"stats": {word_key: {word_stats_dict}}}
        """
        conn = self._get_connection()
        try:
            stats: Dict[str, Any] = {}

            cursor = conn.execute("SELECT * FROM word_stats")
            for row in cursor:
                word_key = row["word_key"]
                word_stats = create_empty_word_stats()
                word_stats["exposed"] = bool(row["exposed"])
                if row["marked_as_known"]:
                    word_stats["markedAsKnown"] = True
                word_stats["practiceHistory"]["lastSeen"] = row["last_seen"]
                word_stats["practiceHistory"]["lastCorrectAnswer"] = row["last_correct_answer"]
                word_stats["practiceHistory"]["lastIncorrectAnswer"] = row["last_incorrect_answer"]
                stats[word_key] = word_stats

            cursor = conn.execute("SELECT * FROM word_activity_stats")
            for row in cursor:
                word_key = row["word_key"]
                if word_key in stats:
                    category = row["category"]
                    activity = row["activity"]
                    if category in stats[word_key] and activity in stats[word_key][category]:
                        stats[word_key][category][activity] = {
                            "correct": row["correct"],
                            "incorrect": row["incorrect"],
                        }

            return {"stats": stats}
        finally:
            conn.close()

    def save_all_stats(self, stats_dict: Dict[str, Any]) -> bool:
        """Replace all word stats from the standard dict format.

        Uses a transaction to atomically replace all data.
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")

            conn.execute("DELETE FROM word_activity_stats")
            conn.execute("DELETE FROM word_stats")

            word_stats_data = stats_dict.get("stats", {})

            for word_key, word_data in word_stats_data.items():
                normalized = validate_and_normalize_word_stats(word_data)

                practice_history = normalized.get("practiceHistory", {})
                conn.execute(
                    """
                    INSERT INTO word_stats
                    (word_key, exposed, marked_as_known,
                     last_seen, last_correct_answer, last_incorrect_answer)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        word_key,
                        1 if normalized.get("exposed", False) else 0,
                        1 if normalized.get("markedAsKnown", False) else 0,
                        practice_history.get("lastSeen"),
                        practice_history.get("lastCorrectAnswer"),
                        practice_history.get("lastIncorrectAnswer"),
                    ),
                )

                for activity in DIRECT_PRACTICE_TYPES:
                    activity_data = normalized.get("directPractice", {}).get(activity, {})
                    correct = activity_data.get("correct", 0)
                    incorrect = activity_data.get("incorrect", 0)
                    conn.execute(
                        """
                        INSERT INTO word_activity_stats
                        (word_key, category, activity, correct, incorrect)
                        VALUES (?, 'directPractice', ?, ?, ?)
                    """,
                        (word_key, activity, correct, incorrect),
                    )

                for activity in CONTEXTUAL_EXPOSURE_TYPES:
                    activity_data = normalized.get("contextualExposure", {}).get(activity, {})
                    correct = activity_data.get("correct", 0)
                    incorrect = activity_data.get("incorrect", 0)
                    conn.execute(
                        """
                        INSERT INTO word_activity_stats
                        (word_key, category, activity, correct, incorrect)
                        VALUES (?, 'contextualExposure', ?, ?, ?)
                    """,
                        (word_key, activity, correct, incorrect),
                    )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving stats to SQLite for user {self.user_id}: {str(e)}")
            return False
        finally:
            conn.close()

    ##########################################################################
    # Daily Snapshot Management
    ##########################################################################

    def snapshot_exists(self, date: str) -> bool:
        """Check if a daily snapshot exists for the given date."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT 1 FROM daily_snapshots WHERE date = ?", (date,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def _compute_current_totals(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Compute current aggregate totals from word_stats tables."""
        cursor = conn.execute("SELECT COUNT(*) FROM word_stats WHERE exposed = 1")
        exposed_count = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM word_stats WHERE marked_as_known = 1")
        words_known_count = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COALESCE(SUM(correct + incorrect), 0) FROM word_activity_stats"
        )
        total_questions = cursor.fetchone()[0]

        cursor = conn.execute(
            """
            SELECT category, activity,
                   SUM(correct) as total_correct,
                   SUM(incorrect) as total_incorrect
            FROM word_activity_stats
            GROUP BY category, activity
        """
        )

        activity_totals: Dict[str, Any] = {
            "directPractice": {a: {"correct": 0, "incorrect": 0} for a in DIRECT_PRACTICE_TYPES},
            "contextualExposure": {
                a: {"correct": 0, "incorrect": 0} for a in CONTEXTUAL_EXPOSURE_TYPES
            },
        }

        for row in cursor:
            category = row["category"]
            activity = row["activity"]
            if category in activity_totals and activity in activity_totals[category]:
                activity_totals[category][activity] = {
                    "correct": row["total_correct"],
                    "incorrect": row["total_incorrect"],
                }

        return {
            "exposed_words_count": exposed_count,
            "words_known_count": words_known_count,
            "total_questions_answered": total_questions,
            "activity_totals": activity_totals,
        }

    def save_snapshot_from_current(self, date: str) -> bool:
        """Create or update a daily snapshot from current word_stats data."""
        conn = self._get_connection()
        try:
            totals = self._compute_current_totals(conn)

            # Compute newly exposed words compared to previous snapshot
            newly_exposed = 0
            cursor = conn.execute(
                """
                SELECT exposed_words_count FROM daily_snapshots
                WHERE date < ? ORDER BY date DESC LIMIT 1
            """,
                (date,),
            )
            prev_row = cursor.fetchone()
            if prev_row:
                newly_exposed = max(
                    0, totals["exposed_words_count"] - prev_row["exposed_words_count"]
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO daily_snapshots
                (date, exposed_words_count, words_known_count, total_questions_answered,
                 newly_exposed_words, activity_totals_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    date,
                    totals["exposed_words_count"],
                    totals["words_known_count"],
                    totals["total_questions_answered"],
                    newly_exposed,
                    json.dumps(totals["activity_totals"], separators=(",", ":")),
                ),
            )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving snapshot for user {self.user_id} date {date}: {str(e)}")
            return False
        finally:
            conn.close()

    def ensure_daily_snapshots(self) -> bool:
        """Ensure daily snapshots exist for today and yesterday."""
        try:
            today = get_current_day_key()
            yesterday = get_yesterday_day_key()

            if not self.snapshot_exists(yesterday):
                self.save_snapshot_from_current(yesterday)

            if not self.snapshot_exists(today):
                self.save_snapshot_from_current(today)

            return True
        except Exception as e:
            logger.error(f"Error ensuring snapshots for user {self.user_id}: {str(e)}")
            return False

    def _get_snapshot(self, date: str) -> Optional[Dict[str, Any]]:
        """Get a daily snapshot for the given date."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM daily_snapshots WHERE date = ?", (date,))
            row = cursor.fetchone()
            if row:
                return {
                    "date": row["date"],
                    "exposed_words_count": row["exposed_words_count"],
                    "words_known_count": row["words_known_count"],
                    "total_questions_answered": row["total_questions_answered"],
                    "newly_exposed_words": row["newly_exposed_words"],
                    "activity_totals_json": row["activity_totals_json"],
                }
            return None
        finally:
            conn.close()

    def _find_best_baseline(self, target_date: str, max_days: int) -> Optional[Dict[str, Any]]:
        """Find the best available baseline snapshot near the target date."""
        conn = self._get_connection()
        try:
            # Try exact date first
            cursor = conn.execute("SELECT * FROM daily_snapshots WHERE date = ?", (target_date,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Search forward from target date within range
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            end_dt = target_dt + timedelta(days=max_days)
            end_date = end_dt.strftime("%Y-%m-%d")

            cursor = conn.execute(
                """
                SELECT * FROM daily_snapshots
                WHERE date > ? AND date <= ?
                ORDER BY date ASC
                LIMIT 1
            """,
                (target_date, end_date),
            )

            row = cursor.fetchone()
            if row:
                return dict(row)

            return None
        finally:
            conn.close()

    def _get_snapshots_in_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get all daily snapshots within a date range."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM daily_snapshots
                WHERE date >= ? AND date <= ?
                ORDER BY date ASC
            """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor]
        finally:
            conn.close()

    ##########################################################################
    # Progress Calculations
    ##########################################################################

    def _empty_activity_totals(self) -> Dict[str, Any]:
        """Return an empty activity totals structure."""
        return {
            "directPractice": {a: {"correct": 0, "incorrect": 0} for a in DIRECT_PRACTICE_TYPES},
            "contextualExposure": {
                a: {"correct": 0, "incorrect": 0} for a in CONTEXTUAL_EXPOSURE_TYPES
            },
        }

    def _compute_progress_from_totals(
        self,
        current_totals: Dict[str, Any],
        baseline_totals: Dict[str, Any],
        current_exposed: int,
        baseline_exposed: int,
    ) -> Dict[str, Any]:
        """Compute progress delta between current and baseline aggregate totals."""
        progress: Dict[str, Any] = {
            "directPractice": {a: {"correct": 0, "incorrect": 0} for a in DIRECT_PRACTICE_TYPES},
            "contextualExposure": {
                a: {"correct": 0, "incorrect": 0} for a in CONTEXTUAL_EXPOSURE_TYPES
            },
            "exposed": {
                "new": max(0, current_exposed - baseline_exposed),
                "total": current_exposed,
            },
        }

        for category in ["directPractice", "contextualExposure"]:
            current_cat = current_totals.get(category, {})
            baseline_cat = baseline_totals.get(category, {})
            activities = (
                DIRECT_PRACTICE_TYPES if category == "directPractice" else CONTEXTUAL_EXPOSURE_TYPES
            )

            for activity in activities:
                cur_act = current_cat.get(activity, {"correct": 0, "incorrect": 0})
                base_act = baseline_cat.get(activity, {"correct": 0, "incorrect": 0})

                progress[category][activity] = {
                    "correct": max(0, cur_act.get("correct", 0) - base_act.get("correct", 0)),
                    "incorrect": max(0, cur_act.get("incorrect", 0) - base_act.get("incorrect", 0)),
                }

        return progress

    def calculate_daily_progress(self) -> Dict[str, Any]:
        """Calculate daily progress (today vs yesterday)."""
        try:
            today = get_current_day_key()
            self.ensure_daily_snapshots()

            conn = self._get_connection()
            try:
                current_totals = self._compute_current_totals(conn)
            finally:
                conn.close()

            yesterday_snapshot = self._get_snapshot(get_yesterday_day_key())
            if yesterday_snapshot:
                baseline_totals = json.loads(yesterday_snapshot["activity_totals_json"])
                baseline_exposed = yesterday_snapshot["exposed_words_count"]
            else:
                baseline_totals = self._empty_activity_totals()
                baseline_exposed = 0

            progress = self._compute_progress_from_totals(
                current_totals["activity_totals"],
                baseline_totals,
                current_totals["exposed_words_count"],
                baseline_exposed,
            )

            return {"currentDay": today, "progress": progress}
        except Exception as e:
            logger.error(f"Error calculating daily progress for user {self.user_id}: {str(e)}")
            return {"error": str(e)}

    def calculate_weekly_progress(self) -> Dict[str, Any]:
        """Calculate weekly progress (current vs 7 days ago)."""
        try:
            today = get_current_day_key()
            week_ago = get_week_ago_day_key()
            self.ensure_daily_snapshots()

            conn = self._get_connection()
            try:
                current_totals = self._compute_current_totals(conn)
            finally:
                conn.close()

            baseline_snapshot = self._find_best_baseline(week_ago, 7)
            if baseline_snapshot:
                baseline_totals = json.loads(baseline_snapshot["activity_totals_json"])
                baseline_exposed = baseline_snapshot["exposed_words_count"]
                actual_baseline_day = baseline_snapshot["date"]
            else:
                baseline_totals = self._empty_activity_totals()
                baseline_exposed = 0
                actual_baseline_day = None

            progress = self._compute_progress_from_totals(
                current_totals["activity_totals"],
                baseline_totals,
                current_totals["exposed_words_count"],
                baseline_exposed,
            )

            return {
                "currentDay": today,
                "targetBaselineDay": week_ago,
                "actualBaselineDay": actual_baseline_day,
                "progress": progress,
            }
        except Exception as e:
            logger.error(f"Error calculating weekly progress for user {self.user_id}: {str(e)}")
            return {"error": str(e)}

    def calculate_monthly_progress(self) -> Dict[str, Any]:
        """Calculate monthly progress with daily breakdown and aggregate."""
        try:
            today = get_current_day_key()
            thirty_days_ago = get_30_days_ago_day_key()
            self.ensure_daily_snapshots()

            conn = self._get_connection()
            try:
                current_totals = self._compute_current_totals(conn)
            finally:
                conn.close()

            # Monthly aggregate
            baseline_snapshot = self._find_best_baseline(thirty_days_ago, 30)
            if baseline_snapshot:
                baseline_totals = json.loads(baseline_snapshot["activity_totals_json"])
                baseline_exposed = baseline_snapshot["exposed_words_count"]
                actual_baseline_day = baseline_snapshot["date"]
            else:
                baseline_totals = self._empty_activity_totals()
                baseline_exposed = 0
                actual_baseline_day = None

            monthly_aggregate = self._compute_progress_from_totals(
                current_totals["activity_totals"],
                baseline_totals,
                current_totals["exposed_words_count"],
                baseline_exposed,
            )

            # Daily data from snapshots
            start_date, end_date = get_30_day_date_range()
            snapshots = self._get_snapshots_in_range(start_date, end_date)
            snapshot_by_date = {s["date"]: s for s in snapshots}

            daily_data: List[Dict[str, Any]] = []
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            current_dt = start_dt

            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                snapshot = snapshot_by_date.get(date_str)

                if snapshot:
                    activity_totals = json.loads(snapshot["activity_totals_json"])
                    daily_data.append(
                        {
                            "date": date_str,
                            "questionsAnswered": snapshot["total_questions_answered"],
                            "exposedWordsCount": snapshot["exposed_words_count"],
                            "newlyExposedWords": snapshot["newly_exposed_words"],
                            "wordsKnown": snapshot["words_known_count"],
                            "activitySummary": build_activity_summary_from_totals(activity_totals),
                        }
                    )
                else:
                    daily_data.append(
                        {
                            "date": date_str,
                            "questionsAnswered": 0,
                            "exposedWordsCount": 0,
                            "newlyExposedWords": 0,
                            "wordsKnown": 0,
                            "activitySummary": empty_activity_summary(),
                        }
                    )

                current_dt += timedelta(days=1)

            period_description = f"Past 30 Days ({start_date} to {end_date})"

            return {
                "currentMonth": period_description,
                "currentDay": today,
                "targetBaselineDay": thirty_days_ago,
                "actualBaselineDay": actual_baseline_day,
                "monthlyAggregate": monthly_aggregate,
                "dailyData": daily_data,
            }
        except Exception as e:
            logger.error(f"Error calculating monthly progress for user {self.user_id}: {str(e)}")
            return {"error": str(e)}


##############################################################################
# High-Level JourneyStats Interface
##############################################################################


class SqliteJourneyStats:
    """Drop-in replacement for JourneyStats using SQLite backend.

    Provides the same interface as JourneyStats (from stats_schema.py)
    but stores data in a SQLite database instead of flat JSON files.
    """

    def __init__(self, user_id: str, language: str = "lithuanian"):
        self.user_id = str(user_id)
        self.language = language
        self._db = SqliteStatsDB(user_id, language)
        self._stats: Optional[Dict[str, Any]] = None
        self._loaded = False

    @property
    def file_path(self) -> str:
        """Get the database file path (for compatibility)."""
        return self._db.db_path

    @property
    def stats(self) -> Dict[str, Any]:
        """Get the stats dictionary. Loads from SQLite if not already loaded."""
        if not self._loaded:
            self.load()
        return self._stats or {"stats": {}}

    @stats.setter
    def stats(self, value: Dict[str, Any]) -> None:
        """Set the stats dictionary."""
        self._stats = value
        self._loaded = True

    def load(self) -> bool:
        """Load stats from SQLite database."""
        try:
            self._stats = self._db.get_all_stats()
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading SQLite stats for user {self.user_id}: {str(e)}")
            self._stats = {"stats": {}}
            self._loaded = True
            return False

    def save(self) -> bool:
        """Save current stats to SQLite database."""
        if not self._loaded or self._stats is None:
            logger.warning(f"Attempting to save unloaded SQLite stats for user {self.user_id}")
            return False
        return self._db.save_all_stats(self._stats)

    def save_with_daily_update(self) -> bool:
        """Save stats and update daily snapshots."""
        try:
            today = get_current_day_key()
            yesterday = get_yesterday_day_key()

            # Ensure yesterday's baseline exists BEFORE saving new data
            if not self._db.snapshot_exists(yesterday):
                self._db.save_snapshot_from_current(yesterday)

            # Save the word stats
            if not self.save():
                return False

            # Update today's snapshot with the new data
            self._db.save_snapshot_from_current(today)

            # Clean up flat file nonces (still stored as flat files)
            from trakaido.blueprints.nonce_utils import cleanup_old_nonce_files

            cleanup_old_nonce_files(self.user_id, self.language)

            return True
        except Exception as e:
            logger.error(
                f"Error in SQLite save_with_daily_update for user {self.user_id}: " f"{str(e)}"
            )
            return False

    def get_word_stats(self, word_key: str) -> Dict[str, Any]:
        """Get stats for a specific word."""
        return self.stats["stats"].get(word_key, {})

    def set_word_stats(self, word_key: str, word_stats: Dict[str, Any]) -> None:
        """Set stats for a specific word (with validation)."""
        if not self._loaded:
            self.load()
        if self._stats is None:
            self._stats = {"stats": {}}
        if "stats" not in self._stats:
            self._stats["stats"] = {}
        self._stats["stats"][word_key] = validate_and_normalize_word_stats(word_stats)

    def is_empty(self) -> bool:
        """Check if the stats are empty."""
        return not bool(self.stats["stats"])
