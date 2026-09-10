import time
from typing import Optional, Callable
from backend.app.video.reader import VideoReader
from backend.app.sampling.base import BaseSampler, SelectionResult, FrameRecord
from backend.app.analysis.quality import compute_quality_metrics

class UniformSampler(BaseSampler):
    """
    Strategy A: Uniform Sampling (Baseline).
    Retains every k-th frame based on target FPS or stride.
    """
    def __init__(self, target_fps: Optional[float] = None, stride: Optional[int] = None):
        self.target_fps = target_fps
        self.stride = stride

    def sample(
        self,
        reader: VideoReader,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SelectionResult:
        start_time = time.time()
        meta = reader.get_metadata()
        total_frames = meta.total_frames
        orig_fps = meta.fps

        # Determine stride or phase accumulator
        use_phase_acc = False
        step = 1.0
        last_phase_int = -1

        if self.stride is not None and self.stride > 0:
            eff_stride = self.stride
            effective_target_fps = round(orig_fps / eff_stride, 2)
        elif self.target_fps is not None and self.target_fps > 0:
            eff_stride = max(1, round(orig_fps / self.target_fps))
            effective_target_fps = min(orig_fps, float(self.target_fps))
            use_phase_acc = True
            step = effective_target_fps / orig_fps if orig_fps > 0 else 1.0
        else:
            eff_stride = 3  # Default 30 FPS -> 10 FPS
            effective_target_fps = round(orig_fps / eff_stride, 2)

        selected_indices = []
        frame_records = []

        for frame_idx, ts, frame in reader.iter_frames(downsample_size=(160, 90)):
            is_first = (frame_idx == 0)
            is_last = (frame_idx == total_frames - 1)

            if use_phase_acc:
                curr_phase_int = int(frame_idx * step)
                should_keep = is_first or is_last or (curr_phase_int > last_phase_int)
                if should_keep and not is_first:
                    last_phase_int = curr_phase_int
            else:
                should_keep = is_first or is_last or (frame_idx % eff_stride == 0)

            if should_keep:
                selected_indices.append(frame_idx)
                reason = "Uniform sampling interval"
            else:
                reason = "Discarded by uniform interval"

            # Compute lightweight quality metrics
            q = compute_quality_metrics(frame)

            record = FrameRecord(
                frame_idx=frame_idx,
                timestamp_sec=ts,
                is_selected=should_keep,
                selection_reason=reason,
                blur_score=q.blur_score,
                brightness=q.brightness,
                contrast=q.contrast,
                is_blurry=q.is_blurry,
                is_underexposed=q.is_underexposed,
                is_overexposed=q.is_overexposed,
            )
            frame_records.append(record)

            if progress_callback and total_frames > 0 and frame_idx % 30 == 0:
                percent = min(100.0, (frame_idx + 1) / total_frames * 100.0)
                progress_callback(percent, f"Uniform sampling: frame {frame_idx}/{total_frames}")

        if progress_callback:
            progress_callback(100.0, "Uniform sampling complete")

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
            strategy_name="uniform",
            parameters={"stride": eff_stride, "target_fps": effective_target_fps},
            total_frames=actual_total_frames,
            selected_indices=selected_indices,
            frame_records=frame_records,
            processing_time_sec=round(duration, 3),
            retention_rate=retention,
            reduction_rate=reduction,
            effective_fps=eff_fps,
        )
