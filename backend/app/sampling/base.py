from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from backend.app.video.reader import VideoReader

@dataclass
class FrameRecord:
    frame_idx: int
    timestamp_sec: float
    is_selected: bool
    selection_reason: str
    similarity_score: Optional[float] = None
    motion_score: Optional[float] = None
    blur_score: Optional[float] = None
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    is_scene_cut: bool = False
    is_blurry: bool = False
    is_underexposed: bool = False
    is_overexposed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_idx": self.frame_idx,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "is_selected": self.is_selected,
            "selection_reason": self.selection_reason,
            "similarity_score": self.similarity_score,
            "motion_score": self.motion_score,
            "blur_score": self.blur_score,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "is_scene_cut": self.is_scene_cut,
            "is_blurry": self.is_blurry,
            "is_underexposed": self.is_underexposed,
            "is_overexposed": self.is_overexposed,
        }

@dataclass
class SelectionResult:
    strategy_name: str
    parameters: Dict[str, Any]
    total_frames: int
    selected_indices: List[int]
    frame_records: List[FrameRecord]
    processing_time_sec: float
    retention_rate: float
    reduction_rate: float
    effective_fps: float

    @property
    def selected_count(self) -> int:
        return len(self.selected_indices)

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "parameters": self.parameters,
            "total_frames": self.total_frames,
            "selected_frames": self.selected_count,
            "retention_rate": round(self.retention_rate, 4),
            "reduction_rate": round(self.reduction_rate, 4),
            "effective_fps": round(self.effective_fps, 2),
            "processing_time_sec": round(self.processing_time_sec, 2),
        }

class BaseSampler(ABC):
    @abstractmethod
    def sample(
        self,
        reader: VideoReader,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SelectionResult:
        """
        Execute frame selection on the given VideoReader.
        progress_callback(percent: float, message: str) can be supplied for status tracking.
        """
        pass
