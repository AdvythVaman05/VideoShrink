import time
from typing import Optional, Callable
import cv2
import numpy as np

from backend.app.video.reader import VideoReader
from backend.app.sampling.base import BaseSampler, SelectionResult, FrameRecord
from backend.app.analysis.similarity import compute_similarity, compute_frame_difference
from backend.app.analysis.quality import compute_quality_metrics

class PerceptualSampler(BaseSampler):
    """
    Strategy B: Perceptual Similarity Sampling.
    Compares consecutive candidate frames against the last retained frame.
    Removes frames that are visually redundant beyond a similarity threshold.
    """
    def __init__(
        self,
        similarity_threshold: float = 0.96,
        max_interval_sec: Optional[float] = 2.5
    ):
        self.similarity_threshold = float(similarity_threshold)
        self.max_interval_sec = max_interval_sec

    def sample(
        self,
        reader: VideoReader,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SelectionResult:
        start_time = time.time()
        meta = reader.get_metadata()
        total_frames = meta.total_frames
        orig_fps = meta.fps

        selected_indices = []
        frame_records = []

        last_kept_frame: Optional[np.ndarray] = None
        last_kept_ts: float = 0.0

        for frame_idx, ts, frame in reader.iter_frames(downsample_size=(160, 90), grayscale=True):
            is_first = (frame_idx == 0)
            is_last = (frame_idx == total_frames - 1)

            sim_score: Optional[float] = None
            diff_score: Optional[float] = None

            if is_first:
                should_keep = True
                reason = "Initial reference frame"
                sim_score = 1.0
            else:
                sim_score = compute_similarity(last_kept_frame, frame)
                diff_score = compute_frame_difference(last_kept_frame, frame)

                interval_exceeded = (
                    self.max_interval_sec is not None
                    and (ts - last_kept_ts) >= self.max_interval_sec
                )

                if is_last:
                    should_keep = True
                    reason = "Terminal video frame"
                elif sim_score < self.similarity_threshold:
                    should_keep = True
                    reason = f"Visual change (sim {sim_score:.2f} < {self.similarity_threshold:.2f})"
                elif interval_exceeded:
                    should_keep = True
                    reason = f"Periodic anchor (gap >= {self.max_interval_sec:.1f}s)"
                else:
                    should_keep = False
                    reason = f"Redundant content (sim {sim_score:.2f})"

            if should_keep:
                selected_indices.append(frame_idx)
                last_kept_frame = frame.copy()
                last_kept_ts = ts

            q = compute_quality_metrics(frame)

            record = FrameRecord(
                frame_idx=frame_idx,
                timestamp_sec=ts,
                is_selected=should_keep,
                selection_reason=reason,
                similarity_score=sim_score,
                blur_score=q.blur_score,
                brightness=q.brightness,
                contrast=q.contrast,
                is_blurry=q.is_blurry,
                is_underexposed=q.is_underexposed,
                is_overexposed=q.is_overexposed,
            )
            frame_records.append(record)

            if progress_callback and total_frames > 0 and frame_idx % 30 == 0:
                pct = min(100.0, (frame_idx + 1) / total_frames * 100.0)
                progress_callback(pct, f"Perceptual similarity: frame {frame_idx}/{total_frames}")

        # Ensure true final frame is retained regardless of header frame count variance
        if frame_records:
            last_frame_idx = frame_records[-1].frame_idx
            if not selected_indices or selected_indices[-1] != last_frame_idx:
                selected_indices.append(last_frame_idx)
                frame_records[-1].is_selected = True
                frame_records[-1].selection_reason = "Terminal frame anchor"

        actual_total_frames = len(frame_records)
        duration = time.time() - start_time
        retention = len(selected_indices) / actual_total_frames if actual_total_frames > 0 else 0.0
        reduction = 1.0 - retention
        eff_fps = (len(selected_indices) / meta.duration_seconds) if meta.duration_seconds > 0 else orig_fps

        return SelectionResult(
            strategy_name="perceptual",
            parameters={
                "similarity_threshold": self.similarity_threshold,
                "max_interval_sec": self.max_interval_sec
            },
            total_frames=actual_total_frames,
            selected_indices=selected_indices,
            frame_records=frame_records,
            processing_time_sec=round(duration, 3),
            retention_rate=retention,
            reduction_rate=reduction,
            effective_fps=eff_fps,
        )
