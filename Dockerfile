FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Install system dependencies: FFmpeg, OpenCV headless libraries, and Nginx reverse proxy
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    nginx \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure storage directories exist with write permissions
RUN mkdir -p data/uploads data/processed data/thumbnails experiments sample_data

# Ensure entrypoint is executable
RUN chmod +x /app/deployment/entrypoint.sh

# Generate synthetic benchmark sample on build for immediate demonstration
RUN python sample_data/generate_sample_video.py

# Expose public container port (Railway binds dynamic $PORT)
EXPOSE 8080

# Production start command routes both FastAPI and Streamlit via Nginx
CMD ["/app/deployment/entrypoint.sh"]
