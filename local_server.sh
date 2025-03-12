#!/bin/bash

# Exit on any error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to project root directory
cd "$SCRIPT_DIR"

# Always build React components
echo "Building React components..."
cd src/web/react
npm ci
npm run build
cd ../../..  # Return to project root

# Set environment variables for development
export FLASK_APP=src/web/server.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Run the development server using launch.py
echo "Starting development server on port 9123..."
python3 launch.py --mode=web --port=9123
