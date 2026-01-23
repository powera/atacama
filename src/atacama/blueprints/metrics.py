"""
Prometheus metrics blueprint for monitoring and observability.

This blueprint exposes a /metrics endpoint that returns metrics in Prometheus format.
Metrics include system stats (CPU, memory, disk), application stats (uptime, content counts),
and HTTP request metrics.
"""

import time

import psutil
from flask import Blueprint, Response, current_app
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

from common.base.logging_config import get_logger

logger = get_logger(__name__)

metrics_bp = Blueprint('metrics', __name__)

# Track server start time
_SERVER_START_TIME = time.time()

# System metrics
cpu_usage_gauge = Gauge(
    'atacama_cpu_usage_percent',
    'Current CPU usage percentage'
)

memory_usage_gauge = Gauge(
    'atacama_memory_usage_percent',
    'Current memory usage percentage'
)

memory_used_bytes = Gauge(
    'atacama_memory_used_bytes',
    'Memory used in bytes'
)

memory_total_bytes = Gauge(
    'atacama_memory_total_bytes',
    'Total memory in bytes'
)

disk_usage_gauge = Gauge(
    'atacama_disk_usage_percent',
    'Current disk usage percentage'
)

disk_used_bytes = Gauge(
    'atacama_disk_used_bytes',
    'Disk space used in bytes'
)

disk_total_bytes = Gauge(
    'atacama_disk_total_bytes',
    'Total disk space in bytes'
)

# Application metrics
uptime_seconds = Gauge(
    'atacama_uptime_seconds',
    'Server uptime in seconds'
)

# Content metrics (will be updated on each /metrics request)
content_count = Gauge(
    'atacama_content_count',
    'Count of content items by type',
    ['content_type']
)

# Database metrics
db_connection_status = Gauge(
    'atacama_database_connected',
    'Database connection status (1=connected, 0=disconnected)'
)

# HTTP request metrics
http_requests_total = Counter(
    'atacama_http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'atacama_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)


def update_system_metrics():
    """Update system-level metrics (CPU, memory, disk)."""
    try:
        cpu_usage_gauge.set(psutil.cpu_percent(interval=0.1))

        memory = psutil.virtual_memory()
        memory_usage_gauge.set(memory.percent)
        memory_used_bytes.set(memory.used)
        memory_total_bytes.set(memory.total)

        disk = psutil.disk_usage('/')
        disk_usage_gauge.set(disk.percent)
        disk_used_bytes.set(disk.used)
        disk_total_bytes.set(disk.total)
    except Exception as e:
        logger.warning(f"Error updating system metrics: {e}")


def update_application_metrics():
    """Update application-level metrics (uptime, content counts)."""
    uptime_seconds.set(time.time() - _SERVER_START_TIME)


def update_database_metrics():
    """Update database-related metrics."""
    try:
        from models.database import db
        from sqlalchemy import text

        with db.session() as db_session:
            db_session.execute(text('SELECT 1'))
            db_connection_status.set(1)
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        db_connection_status.set(0)


def update_content_metrics():
    """Update content count metrics."""
    try:
        from models.database import db
        from models.models import Article, ReactWidget, Email, Quote

        with db.session() as db_session:
            content_count.labels(content_type='emails').set(
                db_session.query(Email).count()
            )
            content_count.labels(content_type='articles').set(
                db_session.query(Article).count()
            )
            content_count.labels(content_type='widgets').set(
                db_session.query(ReactWidget).count()
            )
            content_count.labels(content_type='quotes').set(
                db_session.query(Quote).count()
            )
    except Exception as e:
        logger.warning(f"Error updating content metrics: {e}")


@metrics_bp.route('/metrics')
def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    This endpoint is unauthenticated to allow Prometheus scrapers to access it.

    :return: Prometheus-formatted metrics response
    """
    # Update all metrics before generating output
    update_system_metrics()
    update_application_metrics()
    update_database_metrics()

    # Only update content metrics for BLOG blueprint set to avoid errors in TRAKAIDO mode
    if current_app.config.get('BLUEPRINT_SET') == 'BLOG':
        update_content_metrics()

    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST
    )


def setup_request_metrics(app):
    """
    Set up request timing middleware for HTTP metrics.

    This should be called during app initialization to enable
    per-request metrics collection.

    :param app: Flask application instance
    """
    @app.before_request
    def before_request():
        from flask import g
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        from flask import g, request

        # Skip metrics endpoint to avoid recursion
        if request.endpoint == 'metrics.metrics':
            return response

        # Calculate request duration
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time

            # Get endpoint name, use path if endpoint is None
            endpoint = request.endpoint or request.path

            # Record metrics
            http_requests_total.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

        return response
