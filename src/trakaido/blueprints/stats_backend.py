"""Backend selection and dispatch for Trakaido stats storage.

Supports switching between flat file and SQLite storage backends
on a per-user basis via server_settings.json in the user data directory.

The server_settings.json file lives in the user's data directory:
    data/trakaido/{user_id}/{language}/server_settings.json

Example content:
    {"storage_backend": "flatfile"}

If the file is absent or doesn't specify a valid backend, SQLite storage is used.
"""

# Standard library imports
import json
import os
from typing import Any, Dict, Union

# Local application imports
import constants
from trakaido.blueprints.shared import logger

# Storage backend constants
BACKEND_FLATFILE = "flatfile"
BACKEND_SQLITE = "sqlite"
DEFAULT_BACKEND = BACKEND_SQLITE


def _get_settings_path(user_id: str, language: str = "lithuanian") -> str:
    """Get the path to the user's server_settings.json file."""
    return os.path.join(
        constants.DATA_DIR, "trakaido", str(user_id), language, "server_settings.json"
    )


def get_storage_backend(user_id: str, language: str = "lithuanian") -> str:
    """Determine which storage backend to use for a user.

    Reads server_settings.json from the user's data directory.
    Returns DEFAULT_BACKEND (SQLite) if the file doesn't exist or doesn't
    specify a valid backend.
    """
    settings_path = _get_settings_path(user_id, language)

    if not os.path.exists(settings_path):
        return DEFAULT_BACKEND

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        backend = settings.get("storage_backend", DEFAULT_BACKEND)
        if backend in (BACKEND_SQLITE, BACKEND_FLATFILE):
            return backend
        return DEFAULT_BACKEND
    except Exception as e:
        logger.warning(
            f"Error reading server_settings.json for user {user_id} "
            f"language {language}: {str(e)}. Falling back to {DEFAULT_BACKEND}."
        )
        return DEFAULT_BACKEND


def get_journey_stats(
    user_id: str, language: str = "lithuanian"
) -> Union["JourneyStats", "SqliteJourneyStats"]:
    """Factory function to get the appropriate JourneyStats implementation.

    Returns SqliteJourneyStats if the user is configured for SQLite,
    otherwise returns the standard flat-file JourneyStats.
    """
    backend = get_storage_backend(user_id, language)

    if backend == BACKEND_SQLITE:
        from trakaido.blueprints.stats_sqlite import SqliteJourneyStats

        return SqliteJourneyStats(user_id, language)

    from trakaido.blueprints.stats_schema import JourneyStats

    return JourneyStats(user_id, language)


def ensure_daily_snapshots(user_id: str, language: str = "lithuanian") -> bool:
    """Ensure daily snapshots exist, dispatching to the appropriate backend."""
    backend = get_storage_backend(user_id, language)

    if backend == BACKEND_SQLITE:
        from trakaido.blueprints.stats_sqlite import SqliteStatsDB

        db = SqliteStatsDB(user_id, language)
        result = db.ensure_daily_snapshots()
        # Still clean up flat file nonces (shared with grammar stats)
        from trakaido.blueprints.nonce_utils import cleanup_old_nonce_files

        cleanup_old_nonce_files(user_id, language)
        return result

    from trakaido.blueprints.stats_snapshots import (
        ensure_daily_snapshots as flatfile_ensure,
    )

    return flatfile_ensure(user_id, language)


def calculate_daily_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate daily progress, dispatching to the appropriate backend."""
    backend = get_storage_backend(user_id, language)

    if backend == BACKEND_SQLITE:
        from trakaido.blueprints.stats_sqlite import SqliteStatsDB

        db = SqliteStatsDB(user_id, language)
        return db.calculate_daily_progress()

    from trakaido.blueprints.stats_snapshots import (
        calculate_daily_progress as flatfile_calc,
    )

    return flatfile_calc(user_id, language)


def calculate_weekly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate weekly progress, dispatching to the appropriate backend."""
    backend = get_storage_backend(user_id, language)

    if backend == BACKEND_SQLITE:
        from trakaido.blueprints.stats_sqlite import SqliteStatsDB

        db = SqliteStatsDB(user_id, language)
        return db.calculate_weekly_progress()

    from trakaido.blueprints.stats_snapshots import (
        calculate_weekly_progress as flatfile_calc,
    )

    return flatfile_calc(user_id, language)


def calculate_monthly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate monthly progress, dispatching to the appropriate backend."""
    backend = get_storage_backend(user_id, language)

    if backend == BACKEND_SQLITE:
        from trakaido.blueprints.stats_sqlite import SqliteStatsDB

        db = SqliteStatsDB(user_id, language)
        return db.calculate_monthly_progress()

    from trakaido.blueprints.stats_snapshots import (
        calculate_monthly_progress as flatfile_calc,
    )

    return flatfile_calc(user_id, language)
