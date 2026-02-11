#!/usr/bin/env python3
"""Migrate Trakaido stats from flat-file JSON storage to SQLite.

Reads a user's stats.json and daily snapshot files, then populates a
per-user SQLite database with the equivalent data.

Usage:
    # Migrate a single user (lithuanian is the default language):
    python tools/migrate_flatfile_to_sqlite.py --user USER_ID

    # Migrate a single user for a specific language:
    python tools/migrate_flatfile_to_sqlite.py --user USER_ID --language chinese

    # Migrate all users that still have flat-file data:
    python tools/migrate_flatfile_to_sqlite.py --all

    # Dry run (show what would be migrated, don't write anything):
    python tools/migrate_flatfile_to_sqlite.py --all --dry-run

    # Overwrite existing SQLite database if present:
    python tools/migrate_flatfile_to_sqlite.py --user USER_ID --force
"""

import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

import constants
from trakaido.blueprints.stats_schema import (
    DIRECT_PRACTICE_TYPES,
    CONTEXTUAL_EXPOSURE_TYPES,
    validate_and_normalize_word_stats,
)
from trakaido.blueprints.stats_sqlite import SqliteStatsDB


def get_trakaido_data_dir() -> str:
    """Get the base directory for trakaido user data."""
    return os.path.join(constants.DATA_DIR, "trakaido")


def discover_users(language: str) -> List[str]:
    """Find all user IDs that have flat-file stats for the given language."""
    base_dir = get_trakaido_data_dir()
    if not os.path.isdir(base_dir):
        return []

    users = []
    for user_id in sorted(os.listdir(base_dir)):
        stats_path = os.path.join(base_dir, user_id, language, "stats.json")
        if os.path.isfile(stats_path):
            users.append(user_id)
    return users


def load_flat_file_stats(user_id: str, language: str) -> Optional[Dict[str, Any]]:
    """Load a user's stats.json file."""
    stats_path = os.path.join(
        get_trakaido_data_dir(), user_id, language, "stats.json"
    )
    if not os.path.isfile(stats_path):
        return None

    try:
        with open(stats_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "stats" in data:
            return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARNING: Could not read {stats_path}: {e}")
    return None


def discover_snapshot_dates(user_id: str, language: str) -> List[str]:
    """Find all dates that have daily snapshot files (current type)."""
    daily_dir = os.path.join(
        get_trakaido_data_dir(), user_id, language, "daily"
    )
    if not os.path.isdir(daily_dir):
        return []

    dates = set()
    for filename in os.listdir(daily_dir):
        # Match both {date}_current.json and {date}_current.json.gz
        for suffix in ("_current.json", "_current.json.gz"):
            if filename.endswith(suffix):
                date_part = filename[: -len(suffix)]
                if len(date_part) == 10 and date_part.count("-") == 2:
                    dates.add(date_part)
    return sorted(dates)


def load_snapshot(user_id: str, language: str, date: str) -> Optional[Dict[str, Any]]:
    """Load a daily snapshot file, trying gzip first then plain JSON."""
    daily_dir = os.path.join(
        get_trakaido_data_dir(), user_id, language, "daily"
    )

    gz_path = os.path.join(daily_dir, f"{date}_current.json.gz")
    json_path = os.path.join(daily_dir, f"{date}_current.json")

    try:
        if os.path.isfile(gz_path):
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "stats" in data:
                return data

        if os.path.isfile(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "stats" in data:
                return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARNING: Could not read snapshot {date} for user {user_id}: {e}")

    return None


def compute_snapshot_aggregates(
    stats_data: Dict[str, Any],
) -> Tuple[int, int, Dict[str, Any]]:
    """Compute aggregate totals from a full per-word snapshot.

    Returns:
        (exposed_words_count, total_questions_answered, activity_totals)
    """
    exposed_count = 0
    total_questions = 0
    activity_totals: Dict[str, Any] = {
        "directPractice": {
            a: {"correct": 0, "incorrect": 0} for a in DIRECT_PRACTICE_TYPES
        },
        "contextualExposure": {
            a: {"correct": 0, "incorrect": 0} for a in CONTEXTUAL_EXPOSURE_TYPES
        },
    }

    for word_stats in stats_data.get("stats", {}).values():
        normalized = validate_and_normalize_word_stats(word_stats)

        if normalized.get("exposed", False):
            exposed_count += 1

        for activity in DIRECT_PRACTICE_TYPES:
            act_data = normalized.get("directPractice", {}).get(activity, {})
            correct = act_data.get("correct", 0)
            incorrect = act_data.get("incorrect", 0)
            activity_totals["directPractice"][activity]["correct"] += correct
            activity_totals["directPractice"][activity]["incorrect"] += incorrect
            total_questions += correct + incorrect

        for activity in CONTEXTUAL_EXPOSURE_TYPES:
            act_data = normalized.get("contextualExposure", {}).get(activity, {})
            correct = act_data.get("correct", 0)
            incorrect = act_data.get("incorrect", 0)
            activity_totals["contextualExposure"][activity]["correct"] += correct
            activity_totals["contextualExposure"][activity]["incorrect"] += incorrect
            total_questions += correct + incorrect

    return exposed_count, total_questions, activity_totals


def migrate_user(
    user_id: str, language: str, dry_run: bool = False, force: bool = False
) -> bool:
    """Migrate a single user from flat-file to SQLite.

    Returns True on success, False on failure or skip.
    """
    print(f"  User: {user_id} (language: {language})")

    # Check for existing SQLite database
    db_path = os.path.join(
        get_trakaido_data_dir(), user_id, language, "stats.db"
    )
    if os.path.isfile(db_path) and not force:
        print(f"    SKIPPED: SQLite database already exists at {db_path}")
        print(f"    (use --force to overwrite)")
        return False

    # Load flat-file stats
    stats_data = load_flat_file_stats(user_id, language)
    if stats_data is None:
        print(f"    SKIPPED: No stats.json found")
        return False

    word_count = len(stats_data.get("stats", {}))
    exposed_count = sum(
        1 for w in stats_data.get("stats", {}).values()
        if w.get("exposed", False)
    )
    print(f"    Words: {word_count} ({exposed_count} exposed)")

    # Discover snapshots
    snapshot_dates = discover_snapshot_dates(user_id, language)
    print(f"    Snapshots: {len(snapshot_dates)} daily snapshots found")

    if dry_run:
        print(f"    DRY RUN: Would migrate {word_count} words and {len(snapshot_dates)} snapshots")
        return True

    # Remove existing database if --force
    if os.path.isfile(db_path) and force:
        os.remove(db_path)
        # Also remove WAL and SHM files if they exist
        for suffix in ("-wal", "-shm"):
            wal_path = db_path + suffix
            if os.path.isfile(wal_path):
                os.remove(wal_path)
        print(f"    Removed existing SQLite database")

    # Create SQLite database and save word stats
    db = SqliteStatsDB(user_id, language)
    if not db.save_all_stats(stats_data):
        print(f"    ERROR: Failed to save word stats to SQLite")
        return False
    print(f"    Migrated {word_count} word stats")

    # Migrate daily snapshots
    migrated_snapshots = 0
    prev_exposed_count = 0

    for date in snapshot_dates:
        snapshot_data = load_snapshot(user_id, language, date)
        if snapshot_data is None:
            continue

        exposed, total_q, activity_totals = compute_snapshot_aggregates(snapshot_data)
        newly_exposed = max(0, exposed - prev_exposed_count)
        prev_exposed_count = exposed

        conn = db._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO daily_snapshots
                   (date, exposed_words_count, total_questions_answered,
                    newly_exposed_words, activity_totals_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    date,
                    exposed,
                    total_q,
                    newly_exposed,
                    json.dumps(activity_totals, separators=(",", ":")),
                ),
            )
            conn.commit()
            migrated_snapshots += 1
        except Exception as e:
            print(f"    WARNING: Failed to save snapshot {date}: {e}")
        finally:
            conn.close()

    print(f"    Migrated {migrated_snapshots} daily snapshots")

    # Verify: round-trip the word stats and check counts
    loaded = db.get_all_stats()
    loaded_count = len(loaded.get("stats", {}))
    if loaded_count != word_count:
        print(f"    WARNING: Verification mismatch! Expected {word_count} words, got {loaded_count}")
        return False

    print(f"    Verified: {loaded_count} words in SQLite")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Trakaido stats from flat-file JSON to SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--user", help="Migrate a specific user ID")
    parser.add_argument(
        "--language",
        default="lithuanian",
        help="Language to migrate (default: lithuanian)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="migrate_all",
        help="Migrate all users that have flat-file data",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing SQLite databases",
    )

    args = parser.parse_args()

    if not args.user and not args.migrate_all:
        parser.error("Specify --user USER_ID or --all")

    print(f"Trakaido flat-file to SQLite migration")
    print(f"Data directory: {constants.DATA_DIR}")
    if args.dry_run:
        print(f"Mode: DRY RUN")
    print()

    if args.user:
        users = [args.user]
    else:
        users = discover_users(args.language)
        if not users:
            print(f"No users found with flat-file stats for language '{args.language}'")
            return 0
        print(f"Found {len(users)} users with flat-file stats")
        print()

    success_count = 0
    skip_count = 0
    fail_count = 0

    for user_id in users:
        result = migrate_user(user_id, args.language, args.dry_run, args.force)
        if result:
            success_count += 1
        elif result is False:
            # Could be a skip or a failure -- check if db exists
            db_path = os.path.join(
                get_trakaido_data_dir(), user_id, args.language, "stats.db"
            )
            if os.path.isfile(db_path) and not args.force:
                skip_count += 1
            else:
                fail_count += 1
        print()

    print(f"Migration complete: {success_count} succeeded, {skip_count} skipped, {fail_count} failed")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
