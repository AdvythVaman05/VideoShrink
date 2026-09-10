from backend.app.storage.base import StorageBackend
from backend.app.storage.local import LocalStorageBackend
from backend.app.config import settings

default_storage = LocalStorageBackend(settings.DATA_DIR)

__all__ = ["StorageBackend", "LocalStorageBackend", "default_storage"]
