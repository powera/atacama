from flask import Flask, send_file, render_template_string, send_from_directory, Response
import subprocess
import os
import threading
import time
import logging
from datetime import datetime
from typing import Optional
from waitress import serve  # type: ignore[import-untyped]

import psutil

# Initialize logging
logger = logging.getLogger(__name__)

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

app = Flask(__name__)

# Configuration
BASE_DIR = '/home/atacama/atacama/src/spaceship'
IMAGE_PATH = os.path.join(BASE_DIR, 'current.png')
TEMP_PATH = os.path.join(BASE_DIR, 'temp.png')
GREENLAND_DIR = '/home/atacama/greenland_output/'
UPDATE_INTERVAL = 300  # 5 minutes

class XPlanetGenerator(threading.Thread):
    """Daemon thread to periodically generate new XPlanet images."""
    
    def __init__(self, output_path: str, temp_path: str):
        """
        Initialize the XPlanet generator.
        
        :param output_path: Path to save the final image
        :param temp_path: Path to save temporary image during generation
        """
        super().__init__(daemon=True)
        self.output_path = output_path
        self.temp_path = temp_path
        self.running = True
        
    def generate_image(self) -> bool:
        """
        Generate a new XPlanet image.
        
        :return: True if generation was successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            # Generate new image to temp path
            subprocess.run([
                'xplanet',
                '-output', self.temp_path,
                '-num_times', '1',  # This function is run periodically.
                '-target', 'earth',
                '-origin', 'sun',
                '-geometry', '768x768',
                '-config', '/home/atacama/atacama/src/spaceship/xplanet.conf'
            ], check=True)
            
            # Atomically move to final location
            os.rename(self.temp_path, self.output_path)
            
            logger.info(f"Generated new XPlanet image at {datetime.now()}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"XPlanet generation failed: {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            return False

    def run(self) -> None:
        """Run the generator loop."""
        logger.info("Starting XPlanet generator daemon...")
        
        while self.running:
            self.generate_image()
            time.sleep(UPDATE_INTERVAL)
    
    def stop(self) -> None:
        """Stop the generator gracefully."""
        self.running = False

# Track server start time for uptime metric
_SERVER_START_TIME = time.time()

# Prometheus metrics for Spaceship
spaceship_uptime_seconds = Gauge(
    'spaceship_uptime_seconds',
    'Spaceship server uptime in seconds'
)

spaceship_cpu_usage_percent = Gauge(
    'spaceship_cpu_usage_percent',
    'Current CPU usage percentage'
)

spaceship_memory_usage_percent = Gauge(
    'spaceship_memory_usage_percent',
    'Current memory usage percentage'
)

spaceship_image_age_seconds = Gauge(
    'spaceship_image_age_seconds',
    'Age of the current Earth image in seconds'
)

spaceship_http_requests_total = Counter(
    'spaceship_http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

spaceship_http_request_duration_seconds = Histogram(
    'spaceship_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)


def update_spaceship_metrics():
    """Update Spaceship-specific metrics."""
    spaceship_uptime_seconds.set(time.time() - _SERVER_START_TIME)
    # Use interval=None for non-blocking CPU sampling (returns cached value)
    spaceship_cpu_usage_percent.set(psutil.cpu_percent(interval=None))
    spaceship_memory_usage_percent.set(psutil.virtual_memory().percent)

    # Calculate image age
    try:
        if os.path.exists(IMAGE_PATH):
            image_mtime = os.path.getmtime(IMAGE_PATH)
            spaceship_image_age_seconds.set(time.time() - image_mtime)
    except Exception as e:
        logger.warning(f"Error getting image age: {e}")


# Simple HTML template
LANDING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spaceship Earth</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body {
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: #000;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        .container {
            text-align: center;
        }
        img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 0 20px rgba(255,255,255,0.1);
        }
        p {
            margin-top: 20px;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="container">
        <img src="/earth.png" alt="Current Earth view">
        <p>Updated every 5 minutes • Last update: {{ timestamp }}</p>
    </div>
</body>
</html>
"""

@app.route('/')
def landing_page():
    """Serve the landing page."""
    try:
        timestamp = datetime.fromtimestamp(os.path.getmtime(IMAGE_PATH))
        return render_template_string(
            LANDING_PAGE,
            timestamp=timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        )
    except Exception as e:
        logger.error(f"Error serving landing page: {str(e)}")
        return "Image generation in progress...", 503

@app.route('/earth.png')
def serve_image():
    """Serve the current XPlanet image."""
    try:
        return send_file(IMAGE_PATH, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving image: {str(e)}")
        return "Image not available", 503

@app.route('/greenland/')
def serve_greenland_index():
    """Serve the model_summary.html as the default page for /greenland/"""
    try:
        return send_from_directory(GREENLAND_DIR, 'model_summary.html')
    except Exception as e:
        logger.error(f"Error serving greenland index page: {str(e)}")
        return "Model summary not available", 503

@app.route('/greenland/<path:filename>')
def serve_greenland_files(filename):
    """
    Serve static files from the greenland directory.

    :param filename: Path to the file within the greenland directory
    :return: The requested file
    """
    try:
        return send_from_directory(GREENLAND_DIR, filename)
    except Exception as e:
        logger.error(f"Error serving file from greenland directory: {str(e)}")
        return f"File '{filename}' not found", 404


@app.route('/metrics')
def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.

    :return: Prometheus-formatted metrics response
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(
            "# Prometheus metrics unavailable: prometheus_client not installed\n",
            status=503,
            mimetype="text/plain"
        )

    update_spaceship_metrics()
    return Response(
        generate_latest(REGISTRY),
        mimetype=CONTENT_TYPE_LATEST
    )


def run_server(host: str = '0.0.0.0', port: int = 8998) -> None:
    """
    Run the server with image generator daemon.
    
    :param host: Host address to bind to
    :param port: Port number to listen on
    """
    generator = XPlanetGenerator(IMAGE_PATH, TEMP_PATH)
    generator.start()
    
    logger.info(f"Starting Spaceship server on {host}:{port}")
    try:
        serve(app, host=host, port=port)
    finally:
        generator.stop()
        generator.join()
