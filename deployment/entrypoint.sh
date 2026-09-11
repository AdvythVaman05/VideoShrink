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

# Ensure data and log directories exist
mkdir -p /app/data/uploads /app/data/processed /app/data/thumbnails /app/experiments /app/sample_data /var/log
touch /var/log/uvicorn.log
chmod 666 /var/log/uvicorn.log

# Start FastAPI Uvicorn on internal port 8001 (isolated from public $PORT)
echo "Launching FastAPI (internal 127.0.0.1:8001)..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 > /var/log/uvicorn.log 2>&1 &
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
echo "Waiting for FastAPI backend to become ready on 127.0.0.1:8001..."
FASTAPI_READY=0
for i in {1..40}; do
    if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
        echo "FastAPI backend is healthy and responding on port 8001!"
        FASTAPI_READY=1
        break
    fi
    sleep 0.5
done

if [ "$FASTAPI_READY" -ne 1 ]; then
    echo "=========================================================="
    echo "WARNING: FastAPI failed to respond within 20s. Uvicorn log:"
    cat /var/log/uvicorn.log || true
    echo "=========================================================="
fi

echo "Starting Nginx serving React SPA and reverse proxy on public 0.0.0.0:${PORT}..."
# Run Nginx in foreground (keeps container alive)
nginx -g "daemon off;"
