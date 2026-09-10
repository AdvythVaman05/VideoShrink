from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_obj: BinaryIO, destination_path: str) -> str:
        """Save a file object to destination and return identifier / path."""
        pass

    @abstractmethod
    def get_path(self, identifier: str) -> Path:
        """Get the local filesystem Path to the resource."""
        pass

    @abstractmethod
    def exists(self, identifier: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    def delete(self, identifier: str) -> bool:
        """Delete file if it exists."""
        pass

    @abstractmethod
    def get_size(self, identifier: str) -> int:
        """Get file size in bytes."""
        pass
