from dataclasses import dataclass
from typing import Optional

@dataclass
class ReductionMetrics:
    original_frames: int
    selected_frames: int
    original_size_bytes: int
    compressed_size_bytes: Optional[int]
    original_duration_sec: float
    processing_time_sec: float

    @property
    def frames_removed(self) -> int:
        return self.original_frames - self.selected_frames

    @property
    def frame_reduction_pct(self) -> float:
        if self.original_frames <= 0:
            return 0.0
        return round((self.frames_removed / self.original_frames) * 100.0, 2)

    @property
    def frame_retention_pct(self) -> float:
        if self.original_frames <= 0:
            return 0.0
        return round((self.selected_frames / self.original_frames) * 100.0, 2)

    @property
    def file_size_reduction_pct(self) -> Optional[float]:
        if not self.compressed_size_bytes or self.original_size_bytes <= 0:
            return None
        saved = self.original_size_bytes - self.compressed_size_bytes
        return round((saved / self.original_size_bytes) * 100.0, 2)

    @property
    def effective_fps(self) -> float:
        if self.original_duration_sec <= 0:
            return 0.0
        return round(self.selected_frames / self.original_duration_sec, 2)

    @property
    def frames_per_second_processing(self) -> float:
        if self.processing_time_sec <= 0:
            return 0.0
        return round(self.original_frames / self.processing_time_sec, 1)

    def to_dict(self) -> dict:
        return {
            "original_frames": self.original_frames,
            "selected_frames": self.selected_frames,
            "frames_removed": self.frames_removed,
            "frame_reduction_pct": self.frame_reduction_pct,
            "frame_retention_pct": self.frame_retention_pct,
            "original_size_mb": round(self.original_size_bytes / (1024 * 1024), 2),
            "compressed_size_mb": round(self.compressed_size_bytes / (1024 * 1024), 2) if self.compressed_size_bytes else None,
            "file_size_reduction_pct": self.file_size_reduction_pct,
            "original_duration_sec": self.original_duration_sec,
            "effective_fps": self.effective_fps,
            "processing_time_sec": round(self.processing_time_sec, 2),
            "fps_throughput": self.frames_per_second_processing,
        }
