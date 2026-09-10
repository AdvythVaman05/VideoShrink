import time
from typing import Optional, Callable
import cv2
import numpy as np

from backend.app.video.reader import VideoReader
from backend.app.sampling.base import BaseSampler, SelectionResult, FrameRecord
from backend.app.analysis.motion import compute_motion_energy
from backend.app.analysis.quality import compute_quality_metrics
from backend.app.analysis.similarity import compute_similarity

class MotionAwareSampler(BaseSampler):
    """
    Strategy C: Motion-Aware & Scene-Aware Adaptive Sampling.
    Intelligently modulates sampling frequency based on optical flow motion energy,
    scene cuts, and visual dynamic changes.
    """
    def __init__(
        self,
        motion_sensitivity: float = 0.5,
        min_fps: float = 2.0,
        max_fps: float = 15.0,
        scene_cut_threshold: float = 0.40,
    ):
        self.motion_sensitivity = float(motion_sensitivity)
        self.min_fps = float(min_fps)
        self.max_fps = float(max_fps)
        self.scene_cut_threshold = float(scene_cut_threshold)

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

        prev_frame_gray: Optional[np.ndarray] = None
        last_kept_ts: float = 0.0

        for frame_idx, ts, frame_gray in reader.iter_frames(downsample_size=(160, 90), grayscale=True):
            is_first = (frame_idx == 0)
            is_last = (frame_idx == total_frames - 1)

            motion_score = 0.0
            is_scene_cut = False
            sim_score: Optional[float] = None

            if is_first:
                should_keep = True
                reason = "Initial reference frame"
                last_kept_ts = ts
            else:
                # Compute optical flow motion and scene cut
                motion_data = compute_motion_energy(prev_frame_gray, frame_gray)
                motion_score = motion_data.motion_score
                is_scene_cut = motion_data.is_scene_cut

                sim_score = compute_similarity(prev_frame_gray, frame_gray)

                # Time elapsed since last kept frame
                dt = ts - last_kept_ts

                # Dynamic target FPS based on motion magnitude & sensitivity
                # Boosted motion response
                adjusted_motion = min(1.0, motion_score * (1.0 + self.motion_sensitivity))
                target_fps = self.min_fps + (self.max_fps - self.min_fps) * (adjusted_motion ** 0.8)
                required_interval = 1.0 / max(0.5, target_fps)

                if is_last:
                    should_keep = True
                    reason = "Terminal video frame"
                elif is_scene_cut or (sim_score is not None and sim_score < (1.0 - self.scene_cut_threshold)):
                    should_keep = True
                    is_scene_cut = True
                    reason = f"Scene transition detected (motion={motion_score:.2f}, sim={sim_score:.2f})"
                elif dt >= required_interval:
                    should_keep = True
                    if motion_score >= 0.5:
                        reason = f"High motion burst (score={motion_score:.2f}, target_fps={target_fps:.1f})"
                    elif motion_score >= 0.2:
                        reason = f"Moderate motion activity (score={motion_score:.2f}, target_fps={target_fps:.1f})"
                    else:
                        reason = f"Baseline anchor interval ({self.min_fps:.1f} FPS floor)"
                else:
                    should_keep = False
                    reason = f"Static / redundant motion skipped (score={motion_score:.2f})"

            if should_keep:
                selected_indices.append(frame_idx)
                last_kept_ts = ts

            prev_frame_gray = frame_gray.copy()

            # Quality metrics
            q = compute_quality_metrics(frame_gray)

            record = FrameRecord(
                frame_idx=frame_idx,
                timestamp_sec=ts,
                is_selected=should_keep,
                selection_reason=reason,
                similarity_score=sim_score,
                motion_score=motion_score,
                blur_score=q.blur_score,
                brightness=q.brightness,
                contrast=q.contrast,
                is_scene_cut=is_scene_cut,
                is_blurry=q.is_blurry,
                is_underexposed=q.is_underexposed,
                is_overexposed=q.is_overexposed,
            )
            frame_records.append(record)

            if progress_callback and total_frames > 0 and frame_idx % 30 == 0:
                pct = min(100.0, (frame_idx + 1) / total_frames * 100.0)
                progress_callback(pct, f"Motion analysis: frame {frame_idx}/{total_frames}")

        if progress_callback:
            progress_callback(100.0, "Motion-aware analysis complete")

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
            strategy_name="motion_aware",
            parameters={
                "motion_sensitivity": self.motion_sensitivity,
                "min_fps": self.min_fps,
                "max_fps": self.max_fps,
                "scene_cut_threshold": self.scene_cut_threshold,
            },
            total_frames=actual_total_frames,
            selected_indices=selected_indices,
            frame_records=frame_records,
            processing_time_sec=round(duration, 3),
            retention_rate=retention,
            reduction_rate=reduction,
            effective_fps=eff_fps,
        )
