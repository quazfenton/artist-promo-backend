#!/bin/bash
# Celery worker startup script

echo "Starting Celery worker..."

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start Celery worker with multiple queues
celery -A app.tasks.scraper_tasks worker \
    --loglevel=info \
    --queues=scraping,processing \
    --concurrency=4 \
    --max-tasks-per-child=100 \
    --time-limit=3600 \
    --soft-time-limit=3000

echo "Celery worker stopped."
