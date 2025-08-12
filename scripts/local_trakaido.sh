#!/bin/bash

# Wrapper script to launch Trakaido API server in development mode
# This is a convenience script that calls local_server.sh with trakaido mode

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"

# Call local_server.sh with trakaido mode and any additional arguments
exec "$SCRIPT_DIR/local_server.sh" --mode trakaido "$@"
