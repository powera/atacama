#!/bin/bash

# Exit on any error
set -e

# Change to atacama user's home directory
cd /home/atacama/atacama/

# Pull latest changes from git
git pull

# Build React components
echo "Building React components..."
cd src/web/react
npm ci
npm run build
cd ../../..  # Return to project root

# Restart the systemd service
sudo systemctl restart atacama.service

# Verify the service started successfully
sleep 2
systemctl status atacama.service --no-pager

# Check the logs for startup
journalctl -u atacama.service -n 20 --no-pager
