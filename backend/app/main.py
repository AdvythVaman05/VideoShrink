import sys
from pathlib import Path

# Ensure project root is in sys.path regardless of execution context
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.api.routes import router as api_router
from backend.app.database.mongodb import mongo_manager

logger = logging.getLogger("videoshrink")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB connection if configured
    try:
        mongo_manager.connect()
    except Exception as e:
        logger.warning(f"MongoDB connection startup note: {e}")
    yield
    # Cleanup MongoDB connection on shutdown
    try:
        mongo_manager.close()
    except Exception as e:
        logger.warning(f"MongoDB close note: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="VideoShrink: Information-Preserving Video Dataset Compression API for Computer Vision Datasets.",
    lifespan=lifespan
)

# Enable CORS for local Streamlit and remote frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "description": "Information-Preserving Video Dataset Compression"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mongodb": mongo_manager.check_health()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
