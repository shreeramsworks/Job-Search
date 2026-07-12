#!/bin/bash
# -----------------------------------------------------------------------------
# JobSpy API Server Update & Deployment Script
# This script automates pulling changes from Git and restarting the API service.
# -----------------------------------------------------------------------------

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting Server Update Process ==="

# 1. Navigate to the repository root directory on VPS
# Adjust this path if your installation directory is different
REPO_DIR="/var/www/Job-Search"

if [ -d "$REPO_DIR" ]; then
    echo "Navigating to repository at: $REPO_DIR"
    cd "$REPO_DIR"
else
    echo "ERROR: Directory $REPO_DIR not found. Please run this script from your project root directory."
    exit 1
fi

# 2. Pull the latest changes from GitHub
echo "Pulling latest code from GitHub..."
git pull origin main

# 3. Update python dependencies in virtual environment (if any changed)
if [ -d "jobscraper-actor-main/venv" ]; then
    echo "Updating python packages in virtual environment..."
    ./jobscraper-actor-main/venv/bin/pip install -r jobscraper-actor-main/requirements.txt
else
    echo "Warning: Virtual environment 'venv' not found in jobscraper-actor-main directory. Skipping pip install."
fi

# 4. Restart the systemd background service
echo "Restarting jobspy-api background service..."
sudo systemctl restart jobspy-api

# 5. Output current status of the service
echo "Fetching service status..."
sudo systemctl status jobspy-api --no-pager -n 10

echo "=== Server Update Complete! ==="
