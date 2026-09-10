from pathlib import Path
from typing import Generator, Optional, Tuple
import cv2
import numpy as np

from backend.app.video.metadata import VideoMetadata

class VideoReader:
    """
    Streaming video reader that processes frames sequentially
    without loading entire video into memory.
    """
    def __init__(self, video_path: str | Path):
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
        self._metadata: Optional[VideoMetadata] = None

    def get_metadata(self) -> VideoMetadata:
        """Extract and cache video metadata."""
        if self._metadata is not None:
            return self._metadata

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {self.video_path}. File may be corrupted or format unsupported.")

        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps <= 0 or np.isnan(fps):
                fps = 30.0  # Fallback standard FPS

            duration = total_frames / fps if fps > 0 and total_frames > 0 else 0.0
            file_size = self.video_path.stat().st_size

            # Codec string
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip()

            bitrate_kbps = (file_size * 8 / (duration * 1000)) if duration > 0 else None

            self._metadata = VideoMetadata(
                filename=self.video_path.name,
                filepath=str(self.video_path),
                width=width,
                height=height,
                fps=round(fps, 2),
                total_frames=total_frames,
                duration_seconds=round(duration, 2),
                file_size_bytes=file_size,
                codec=codec if codec else "unknown",
                bitrate_kbps=round(bitrate_kbps, 2) if bitrate_kbps else None,
            )
            return self._metadata
        finally:
            cap.release()

    def iter_frames(
        self,
        downsample_size: Optional[Tuple[int, int]] = (160, 90),
        grayscale: bool = False
    ) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        Streaming generator yielding (frame_idx, timestamp_sec, processed_frame).
        Memory efficient: yields downsampled/processed frame, releases original.
        """
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {self.video_path}")

        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0 or np.isnan(fps):
            fps = 30.0

        frame_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                timestamp = frame_idx / fps

                if downsample_size is not None:
                    frame = cv2.resize(frame, downsample_size, interpolation=cv2.INTER_AREA)

                if grayscale:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                yield frame_idx, timestamp, frame
                frame_idx += 1
        finally:
            cap.release()

    def extract_frame_at(self, target_idx: int) -> Optional[np.ndarray]:
        """Extract a single full-resolution frame by index (RGB format for preview/saving)."""
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            return None
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return None
        finally:
            cap.release()
