from flask import Flask, send_file, render_template_string
import subprocess
import os
import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from waitress import serve

# Initialize logging
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
BASE_DIR = '/home/atacama/atacama/spaceship'
IMAGE_PATH = os.path.join(BASE_DIR, 'current.png')
TEMP_PATH = os.path.join(BASE_DIR, 'temp.png')
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
                '-wait', '30',
                '-num_times', '1',  # This function is run periodically.
                '-body', 'earth',
                '-target', 'earth',
                '-origin', 'sun',
                '-geometry', '1024x1024',
                '-config', '/home/atacama/atacama/spaceship/xplanet.conf'
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
