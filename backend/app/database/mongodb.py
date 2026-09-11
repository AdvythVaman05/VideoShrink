import re
import logging
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError

from backend.app.config import settings

logger = logging.getLogger("videoshrink.mongodb")

def mask_mongo_uri(uri: Optional[str]) -> str:
    """Safely mask password in MongoDB URI for logging."""
    if not uri:
        return "None"
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", uri)

class MongoDBManager:
    _instance: Optional["MongoDBManager"] = None
    _client: Optional[MongoClient] = None
    _database: Optional[Database] = None
    _is_initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBManager, cls).__new__(cls)
        return cls._instance

    @property
    def is_configured(self) -> bool:
        return bool(settings.MONGODB_URI and settings.MONGODB_URI.strip())

    @property
    def client(self) -> Optional[MongoClient]:
        return self._client

    @property
    def database(self) -> Optional[Database]:
        if self._database is None and self.is_configured:
            self.connect()
        return self._database

    def connect(self) -> bool:
        """Initializes connection to MongoDB Atlas with connection pooling and timeouts."""
        if not self.is_configured:
            logger.info("MongoDB is not configured (MONGODB_URI unset). Operating in local fallback mode.")
            return False

        if self._client is not None:
            return True

        masked = mask_mongo_uri(settings.MONGODB_URI)
        logger.info(f"Connecting to MongoDB Atlas at {masked}...")

        try:
            # Use PyMongo ServerApi v1 and strict timeouts for production resilience
            server_api = ServerApi(version="1", strict=True, deprecation_errors=True)
            self._client = MongoClient(
                settings.MONGODB_URI,
                server_api=server_api,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5,
                appname="VideoShrink"
            )

            # Test connection with ping command
            self._client.admin.command("ping")
            db_name = settings.MONGODB_DATABASE or "videoshrink"
            self._database = self._client[db_name]
            self._is_initialized = True
            logger.info(f"Successfully connected to MongoDB database: {db_name}")

            # Create required indexes idempotently
            self._ensure_indexes()
            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection timeout or failure: {type(e).__name__}. Operating in local fallback mode.")
            self._client = None
            self._database = None
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {type(e).__name__}. Operating in local fallback mode.")
            self._client = None
            self._database = None
            return False

    def _ensure_indexes(self) -> None:
        """Idempotently creates necessary indexes on videos, jobs, and experiments collections."""
        if self._database is None:
            return
        try:
            # 1. videos collection indexes
            videos = self._database["videos"]
            videos.create_index([("video_id", ASCENDING)], unique=True, name="idx_videos_video_id")
            videos.create_index([("created_at", ASCENDING)], name="idx_videos_created_at")

            # 2. jobs collection indexes
            jobs = self._database["jobs"]
            jobs.create_index([("job_id", ASCENDING)], unique=True, name="idx_jobs_job_id")
            jobs.create_index([("video_id", ASCENDING)], name="idx_jobs_video_id")
            jobs.create_index([("status", ASCENDING)], name="idx_jobs_status")
            jobs.create_index([("created_at", ASCENDING)], name="idx_jobs_created_at")

            # 3. experiments collection indexes
            experiments = self._database["experiments"]
            experiments.create_index([("id", ASCENDING)], unique=True, name="idx_experiments_id")
            experiments.create_index([("experiment_code", ASCENDING)], name="idx_experiments_code")
            experiments.create_index([("created_at", ASCENDING)], name="idx_experiments_created_at")
            experiments.create_index([("video_filename", ASCENDING)], name="idx_experiments_video_filename")

            logger.info("MongoDB indexes verified and created idempotently.")
        except PyMongoError as e:
            logger.warning(f"Could not create MongoDB indexes: {e}")

    def check_health(self) -> dict:
        """
        Checks connection status without leaking credentials.
        Returns structured dict with 'status' and 'fallback_mode'.
        """
        if not self.is_configured:
            return {"status": "not_configured", "fallback_mode": True}
        if self._client is None:
            connected = self.connect()
            if not connected:
                return {"status": "unavailable", "fallback_mode": True}
        try:
            self._client.admin.command("ping")
            return {"status": "connected", "database": settings.MONGODB_DATABASE, "fallback_mode": False}
        except Exception:
            return {"status": "unavailable", "fallback_mode": True}

    def close(self) -> None:
        """Gracefully closes the MongoDB client connections on application shutdown."""
        if self._client is not None:
            logger.info("Closing MongoDB client connection...")
            self._client.close()
            self._client = None
            self._database = None
            self._is_initialized = False

mongo_manager = MongoDBManager()

def get_mongo_db() -> Optional[Database]:
    return mongo_manager.database

def get_mongo_client() -> Optional[MongoClient]:
    return mongo_manager.client
