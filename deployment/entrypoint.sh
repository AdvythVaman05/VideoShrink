#!/usr/bin/env bash
set -e

# Respect dynamic Railway PORT or default to 8080
export PORT="${PORT:-8080}"
export PYTHONPATH="/app:${PYTHONPATH}"
cd /app

echo "=========================================================="
echo "Starting VideoShrink Production Environment on PORT ${PORT}"
echo "=========================================================="

# Remove default nginx site to avoid port 80 conflicts
rm -f /etc/nginx/sites-enabled/default

# Generate Nginx configuration from template
envsubst '${PORT}' < /app/deployment/nginx.conf.template > /etc/nginx/conf.d/videoshrink.conf

# Verify Nginx configuration syntax
nginx -t

# Ensure data directories exist
mkdir -p /app/data/uploads /app/data/processed /app/data/thumbnails /app/experiments /app/sample_data

# Start FastAPI Uvicorn on internal port 8000
echo "Launching FastAPI (internal 127.0.0.1:8000)..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
FASTAPI_PID=$!

# Trap termination signals to cleanly shut down child processes
cleanup() {
    echo "Received termination signal. Shutting down child processes..."
    kill -TERM "$FASTAPI_PID" 2>/dev/null || true
    wait "$FASTAPI_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for FastAPI to be ready before accepting public traffic
echo "Waiting for FastAPI backend to become ready..."
for i in {1..30}; do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "FastAPI backend is healthy and responding!"
        break
    fi
    sleep 0.5
done

echo "Starting Nginx serving React SPA on public 0.0.0.0:${PORT}..."
# Run Nginx in foreground (keeps container alive)
nginx -g "daemon off;"
