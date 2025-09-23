#!/bin/bash

# Exit on any error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to project root directory
cd "$SCRIPT_DIR"

# Default values
MODE="web"
PORT="9123"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --http-debug)
            export ATACAMA_HTTP_DEBUG=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--mode web|trakaido] [--port PORT] [--http-debug]"
            exit 1
            ;;
    esac
done

# Set default ports based on mode if not specified
if [[ "$MODE" == "trakaido" && "$PORT" == "9123" ]]; then
    PORT="9124"
fi

# Set environment variables for development
export FLASK_APP=src/web/server.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Enable request logging to console for development
export ATACAMA_REQUEST_LOG_CONSOLE=1

# Run the development server using launch.py
echo "Starting development $MODE server on port $PORT..."
echo "Request logs will be output to console (STDERR)"
if [[ -n "$ATACAMA_HTTP_DEBUG" ]]; then
    echo "HTTP debug logging enabled - LLM API requests/responses will be logged (first 512 bytes)"
fi
python3 launch.py --mode="$MODE" --port="$PORT" --log-level=DEBUG
