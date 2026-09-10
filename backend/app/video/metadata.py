from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class VideoMetadata:
    filename: str
    filepath: str
    width: int
    height: int
    fps: float
    total_frames: int
    duration_seconds: float
    file_size_bytes: int
    codec: Optional[str] = None
    bitrate_kbps: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 2)

    @property
    def duration_formatted(self) -> str:
        mins = int(self.duration_seconds // 60)
        secs = self.duration_seconds % 60
        return f"{mins:02d}:{secs:05.2f}"
