import shutil
from pathlib import Path
from typing import BinaryIO
from backend.app.storage.base import StorageBackend

class LocalStorageBackend(StorageBackend):
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_obj: BinaryIO, relative_path: str) -> str:
        dest = self.root_dir / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return str(dest)

    def save_bytes(self, data: bytes, relative_path: str) -> str:
        dest = self.root_dir / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return str(dest)

    def get_path(self, relative_or_absolute: str) -> Path:
        p = Path(relative_or_absolute)
        if p.is_absolute():
            return p
        return self.root_dir / relative_or_absolute

    def exists(self, relative_or_absolute: str) -> bool:
        return self.get_path(relative_or_absolute).is_file()

    def delete(self, relative_or_absolute: str) -> bool:
        path = self.get_path(relative_or_absolute)
        if path.is_file():
            path.unlink()
            return True
        return False

    def get_size(self, relative_or_absolute: str) -> int:
        path = self.get_path(relative_or_absolute)
        if path.is_file():
            return path.stat().st_size
        return 0
