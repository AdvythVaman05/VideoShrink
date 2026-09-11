from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "VideoShrink"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    
    # Storage and paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    PROCESSED_DIR: Path = DATA_DIR / "processed"
    THUMBNAIL_DIR: Path = DATA_DIR / "thumbnails"
    DB_PATH: Path = BASE_DIR / "experiments" / "videoshrink.db"
    
    # Limits for MVP safety and performance
    MAX_UPLOAD_SIZE_MB: int = 250
    MAX_VIDEO_DURATION_SEC: int = 1800  # 30 minutes
    ANALYSIS_FRAME_SIZE: tuple[int, int] = (160, 90)  # downsampled width x height for fast streaming metrics
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB Atlas settings
    MONGODB_URI: str | None = None
    MONGODB_DATABASE: str = "videoshrink"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
