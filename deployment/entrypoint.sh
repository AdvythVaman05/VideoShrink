#!/usr/bin/env bash
set -e

# Respect dynamic Railway PORT or default to 8080
export PORT="${PORT:-8080}"
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
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 &
FASTAPI_PID=$!

# Start Streamlit on internal port 8501
echo "Launching Streamlit (internal 127.0.0.1:8501)..."
streamlit run frontend/streamlit_app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false &
STREAMLIT_PID=$!

# Trap termination signals to cleanly shut down child processes
cleanup() {
    echo "Received termination signal. Shutting down child processes..."
    kill -TERM "$FASTAPI_PID" "$STREAMLIT_PID" 2>/dev/null || true
    wait "$FASTAPI_PID" 2>/dev/null || true
    wait "$STREAMLIT_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "Starting Nginx reverse proxy on public 0.0.0.0:${PORT}..."
# Run Nginx in foreground (keeps container alive)
nginx -g "daemon off;"
