"""Trakaido-specific Prometheus metrics."""

import time
from threading import Lock

from common.base.logging_config import get_logger
from common.config.language_config import get_language_manager

logger = get_logger(__name__)

try:
    from prometheus_client import Gauge
except ImportError:
    logger.warning(
        "prometheus_client is not installed. Trakaido metrics will be unavailable. "
        "Install with: pip install prometheus_client"
    )

    class Gauge:
        """No-op Gauge stub when prometheus_client is unavailable."""

        def __init__(self, *args, **kwargs):
            pass

        def set(self, value):
            pass


trakaido_total_users = Gauge(
    "atacama_trakaido_total_users", "Total number of users in the Trakaido user database"
)

trakaido_active_users_last_hour = Gauge(
    "atacama_trakaido_active_users_last_hour",
    "Number of distinct Trakaido users active in the last hour (in-memory, per server)",
)

trakaido_active_users_by_language = Gauge(
    "atacama_trakaido_active_users_by_language",
    "Number of distinct Trakaido users active in the last hour by language (in-memory, per server)",
    ["language"],
)

_ACTIVE_WINDOW_SECONDS = 3600
_activity_lock = Lock()
_user_last_seen: dict[str, tuple[float, str]] = {}


def record_trakaido_activity(user_id: str, language: str) -> None:
    """Record in-memory user activity for active-user metrics."""
    if not user_id:
        return

    normalized_language = language or "unknown"
    with _activity_lock:
        _user_last_seen[user_id] = (time.time(), normalized_language)


def _compute_active_user_snapshot() -> tuple[int, dict[str, int]]:
    """Compute active-user counts over the rolling active window."""
    cutoff = time.time() - _ACTIVE_WINDOW_SECONDS
    active_by_language: dict[str, int] = {}

    with _activity_lock:
        stale_user_ids = []
        for user_id, (last_seen_ts, language) in _user_last_seen.items():
            if last_seen_ts < cutoff:
                stale_user_ids.append(user_id)
                continue
            active_by_language[language] = active_by_language.get(language, 0) + 1

        for user_id in stale_user_ids:
            _user_last_seen.pop(user_id, None)

    return sum(active_by_language.values()), active_by_language


def update_trakaido_metrics():
    """Update Trakaido-specific metrics."""
    try:
        from models.database import db
        from models.models import User

        with db.session() as db_session:
            trakaido_total_users.set(db_session.query(User).count())

        active_total, active_by_language = _compute_active_user_snapshot()
        trakaido_active_users_last_hour.set(active_total)

        # Initialize configured languages to zero so label series are stable.
        for language in get_language_manager().get_all_language_keys():
            trakaido_active_users_by_language.labels(language=language).set(0)

        for language, count in active_by_language.items():
            trakaido_active_users_by_language.labels(language=language).set(count)
    except Exception as e:
        logger.warning(f"Error updating Trakaido metrics: {e}")
