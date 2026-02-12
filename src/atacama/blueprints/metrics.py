"""
Prometheus metrics blueprint for monitoring and observability.

This blueprint exposes a /metrics endpoint that returns metrics in Prometheus format.
Metrics include system stats (CPU, memory, disk, network), application stats (uptime,
content counts), process stats (threads, file descriptors), and HTTP request metrics.

The prometheus_client library is optional. If not installed, the server will start
but the /metrics endpoint will return an error message.
"""

import os
import time

import psutil
from flask import Blueprint, Response, current_app

from common.base.logging_config import get_logger

logger = get_logger(__name__)

# Try to import prometheus_client, fall back to no-op stubs if unavailable
PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.error(
        "prometheus_client is not installed. Metrics will be unavailable. "
        "Install with: pip install prometheus_client"
    )

    # No-op stub classes for when prometheus_client is not available
    class _NoOpMetric:
        """No-op metric that silently ignores all operations."""

        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, amount=1):
            pass

        def dec(self, amount=1):
            pass

        def set(self, value):
            pass

        def observe(self, value):
            pass

    class Gauge(_NoOpMetric):
        """No-op Gauge stub."""
        pass

    class Counter(_NoOpMetric):
        """No-op Counter stub."""
        pass

    class Histogram(_NoOpMetric):
        """No-op Histogram stub."""
        pass

    def generate_latest(registry=None):
        return b""

    CONTENT_TYPE_LATEST = "text/plain"
    REGISTRY = None

metrics_bp = Blueprint('metrics', __name__)

# Track server start time
_SERVER_START_TIME = time.time()

# Get process for process-specific metrics
_PROCESS = psutil.Process(os.getpid())

# System metrics
cpu_usage_gauge = Gauge(
    'atacama_cpu_usage_percent',
    'Current CPU usage percentage (non-blocking snapshot)'
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

# Network I/O metrics
network_bytes_sent = Gauge(
    'atacama_network_bytes_sent_total',
    'Total bytes sent over network'
)

network_bytes_recv = Gauge(
    'atacama_network_bytes_recv_total',
    'Total bytes received over network'
)

# Process-specific metrics
process_cpu_percent = Gauge(
    'atacama_process_cpu_percent',
    'CPU usage of this process'
)

process_memory_bytes = Gauge(
    'atacama_process_memory_bytes',
    'Memory usage of this process in bytes'
)

process_threads = Gauge(
    'atacama_process_threads',
    'Number of threads in this process'
)

process_open_fds = Gauge(
    'atacama_process_open_fds',
    'Number of open file descriptors'
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

# Error tracking
http_errors_total = Counter(
    'atacama_http_errors_total',
    'Total number of HTTP errors (4xx and 5xx)',
    ['status_class']
)

# Authentication metrics
auth_logins_total = Counter(
    'atacama_auth_logins_total',
    'Total number of login attempts',
    ['provider', 'status']  # provider: google, debug; status: success, failure
)

auth_logouts_total = Counter(
    'atacama_auth_logouts_total',
    'Total number of logouts'
)

# Database latency metrics
db_session_duration_seconds = Histogram(
    'atacama_db_session_duration_seconds',
    'Database session duration in seconds',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

db_query_errors_total = Counter(
    'atacama_db_query_errors_total',
    'Total number of database query errors'
)


def record_login(provider: str, success: bool):
    """
    Record a login attempt for metrics.

    :param provider: Authentication provider (e.g., 'google', 'debug')
    :param success: Whether the login was successful
    """
    status = 'success' if success else 'failure'
    auth_logins_total.labels(provider=provider, status=status).inc()


def record_logout():
    """Record a logout event for metrics."""
    auth_logouts_total.inc()


def record_db_session_duration(duration: float):
    """
    Record database session duration for metrics.

    :param duration: Session duration in seconds
    """
    db_session_duration_seconds.observe(duration)


def record_db_error():
    """Record a database error for metrics."""
    db_query_errors_total.inc()


def update_system_metrics():
    """Update system-level metrics (CPU, memory, disk, network)."""
    try:
        # Use interval=None for non-blocking CPU sampling (returns cached value)
        # This avoids the 100ms+ blocking call on each scrape
        cpu_usage_gauge.set(psutil.cpu_percent(interval=None))

        memory = psutil.virtual_memory()
        memory_usage_gauge.set(memory.percent)
        memory_used_bytes.set(memory.used)
        memory_total_bytes.set(memory.total)

        disk = psutil.disk_usage('/')
        disk_usage_gauge.set(disk.percent)
        disk_used_bytes.set(disk.used)
        disk_total_bytes.set(disk.total)

        # Network I/O counters
        net_io = psutil.net_io_counters()
        network_bytes_sent.set(net_io.bytes_sent)
        network_bytes_recv.set(net_io.bytes_recv)
    except Exception as e:
        logger.warning(f"Error updating system metrics: {e}")


def update_process_metrics():
    """Update process-specific metrics (CPU, memory, threads, file descriptors)."""
    try:
        process_cpu_percent.set(_PROCESS.cpu_percent())
        process_memory_bytes.set(_PROCESS.memory_info().rss)
        process_threads.set(_PROCESS.num_threads())

        # File descriptors (Unix only)
        try:
            process_open_fds.set(_PROCESS.num_fds())
        except AttributeError:
            # num_fds() not available on Windows
            pass
    except Exception as e:
        logger.warning(f"Error updating process metrics: {e}")


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
    if not PROMETHEUS_AVAILABLE:
        return Response(
            "# Prometheus metrics unavailable: prometheus_client not installed\n",
            status=503,
            mimetype="text/plain"
        )

    # Update all metrics before generating output
    update_system_metrics()
    update_process_metrics()
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

    If prometheus_client is not available, this function does nothing.

    :param app: Flask application instance
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Skipping request metrics setup: prometheus_client not installed")
        return

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

            # Skip 404 responses to avoid polluting metrics with
            # spammy requests to nonexistent paths (e.g., xax.php, b.php)
            if response.status_code == 404:
                return response

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

            # Track errors by class (4xx, 5xx)
            if response.status_code >= 400:
                status_class = '4xx' if response.status_code < 500 else '5xx'
                http_errors_total.labels(status_class=status_class).inc()

        return response
