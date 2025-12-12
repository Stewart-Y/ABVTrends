#!/bin/bash
set -e

# Run Alembic migrations if RUN_MIGRATIONS is set to true
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
