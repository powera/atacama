#!/bin/bash

# Exit on any error
set -e

# Change to atacama user's home directory
cd /home/atacama/atacama/

# Pull latest changes from git
git pull --recurse-submodules

# Restart the systemd service
sudo systemctl restart blog.service

# Verify the service started successfully
sleep 2
systemctl status blog.service --no-pager

# Check the logs for startup
journalctl -u blog.service -n 20 --no-pager
