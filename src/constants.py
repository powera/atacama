import os

# Get the src directory
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# Define common paths relative to project root
WEB_DIR = os.path.join(SRC_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
KEY_DIR = os.path.join(PROJECT_ROOT, "keys")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")
