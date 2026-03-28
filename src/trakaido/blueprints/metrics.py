"""Trakaido-specific Prometheus metrics."""

from common.base.logging_config import get_logger

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


def update_trakaido_metrics():
    """Update Trakaido-specific metrics."""
    try:
        from models.database import db
        from models.models import User

        with db.session() as db_session:
            trakaido_total_users.set(db_session.query(User).count())
    except Exception as e:
        logger.warning(f"Error updating Trakaido metrics: {e}")
