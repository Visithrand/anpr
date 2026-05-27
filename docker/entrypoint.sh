#!/bin/bash
# ==============================================================================
# ANPR.OS — Docker Entrypoint
# ==============================================================================
# Waits for PostgreSQL, then starts the backend.
# ==============================================================================

set -e

echo "================================================="
echo "  ANPR.OS — Docker Entrypoint"
echo "================================================="

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
    conn.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo "PostgreSQL is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Waiting for PostgreSQL... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: PostgreSQL did not become ready in time."
    exit 1
fi

# Create required directories
mkdir -p logs static/plates snapshots

echo "Starting ANPR.OS Backend..."
echo "================================================="

# Start uvicorn
exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info \
    --timeout-keep-alive 65
