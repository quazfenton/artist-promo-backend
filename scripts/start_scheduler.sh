#!/bin/bash
# Celery beat scheduler startup script

echo "Starting Celery beat scheduler..."

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start Celery beat scheduler
celery -A app.tasks.scraper_tasks beat \
    --loglevel=info \
    --schedule=/tmp/celerybeat-schedule \
    --pidfile=/tmp/celerybeat.pid

echo "Celery beat scheduler stopped."
