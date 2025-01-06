import os

# Get the src directory
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

# Define common paths relative to project root
WEB_DIR = os.path.join(SRC_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
