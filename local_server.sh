#!/bin/bash

# Exit on any error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to project root directory
cd "$SCRIPT_DIR"

# Set environment variables for development
export FLASK_APP=src/web/server.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Enable request logging to console for development
export ATACAMA_REQUEST_LOG_CONSOLE=1

# Run the development server using launch.py
echo "Starting development server on port 9123..."
echo "Request logs will be output to console (STDERR)"
python3 launch.py --mode=web --port=9123 --log-level=DEBUG
