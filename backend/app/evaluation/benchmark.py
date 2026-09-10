from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
import numpy as np

from backend.app.video.reader import VideoReader
from backend.app.sampling.base import SelectionResult

@dataclass
class VisualPreservationProxyResult:
    """
    Visual/Data Preservation Proxy Metric.
    IMPORTANT: This is an analytical proxy heuristic measuring temporal
    sampling properties (peak motion coverage, temporal dispersion, sharpness ratio).
    It is NOT equivalent to downstream ML performance. Downstream model performance
    can only be claimed when an actual vision model is evaluated on both datasets.
    """
    metric_name: str = "Visual/Data Preservation Proxy Metric"
    proxy_fidelity_score: float = 0.0      # [0.0, 1.0] Proxy heuristic
    motion_coverage_score: float = 0.0     # [0.0, 1.0] Proportion of high-motion peaks sampled
    temporal_coverage_score: float = 0.0   # [0.0, 1.0] Temporal uniformity / absence of blindspots
    sharpness_preservation_ratio: float = 0.0 # [0.0, 1.0] Proportion of selected frames that are sharp
    disclaimer: str = (
        "PROXY METRIC ONLY: This score quantifies visual motion and temporal coverage heuristics. "
        "It does NOT guarantee or measure downstream computer vision ML model accuracy (e.g. mAP, Top-1), "
        "which requires evaluating a trained neural network on the downstream task."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "proxy_fidelity_score": round(self.proxy_fidelity_score, 3),
            "motion_coverage_score": round(self.motion_coverage_score, 3),
            "temporal_coverage_score": round(self.temporal_coverage_score, 3),
            "sharpness_preservation_ratio": round(self.sharpness_preservation_ratio, 3),
            "disclaimer": self.disclaimer,
        }

class VisualPreservationProxyEvaluator:
    """
    Deterministic visual proxy evaluator.
    Analyzes whether the pruned frame selection captured:
    1. Motion peaks from the original stream
    2. Even temporal distribution without severe temporal dropouts
    3. Sharp frames over blurred frames
    """
    def evaluate(self, reader: VideoReader, selection: SelectionResult) -> VisualPreservationProxyResult:
        records = selection.frame_records
        if not records or selection.total_frames <= 0:
            return VisualPreservationProxyResult()

        selected_indices = set(selection.selected_indices)

        # 1. Motion Peak Coverage
        motion_scores = [r.motion_score or 0.0 for r in records]
        if motion_scores:
            high_motion_cutoff = float(np.percentile(motion_scores, 85))
            peak_indices = [r.frame_idx for r in records if (r.motion_score or 0.0) >= high_motion_cutoff]
            if peak_indices:
                covered = sum(1 for p in peak_indices if any(abs(s - p) <= 2 for s in selected_indices))
                motion_coverage = covered / len(peak_indices)
            else:
                motion_coverage = 1.0
        else:
            motion_coverage = 1.0

        # 2. Temporal continuity (penalize extreme gaps > 4s)
        meta = reader.get_metadata()
        fps = meta.fps if meta.fps > 0 else 30.0
        max_gap_frames = int(fps * 4.0)

        sorted_sel = sorted(list(selected_indices))
        if len(sorted_sel) > 1:
            gaps = [sorted_sel[i+1] - sorted_sel[i] for i in range(len(sorted_sel)-1)]
            excessive_gaps = sum(1 for g in gaps if g > max_gap_frames)
            temporal_coverage = max(0.0, 1.0 - (excessive_gaps / len(gaps)))
        else:
            temporal_coverage = 0.5

        # 3. Sharpness preservation
        kept_records = [r for r in records if r.is_selected]
        if kept_records:
            sharp_count = sum(1 for r in kept_records if not r.is_blurry)
            sharp_ratio = sharp_count / len(kept_records)
        else:
            sharp_ratio = 1.0

        composite_proxy = (
            0.45 * motion_coverage +
            0.35 * temporal_coverage +
            0.20 * sharp_ratio
        )

        return VisualPreservationProxyResult(
            proxy_fidelity_score=round(float(np.clip(composite_proxy, 0.0, 1.0)), 3),
            motion_coverage_score=round(float(motion_coverage), 3),
            temporal_coverage_score=round(float(temporal_coverage), 3),
            sharpness_preservation_ratio=round(float(sharp_ratio), 3),
        )

# =====================================================================
# Phase 2 Downstream Machine Learning Benchmark Interface
# =====================================================================

class DownstreamMLBenchmark(ABC):
    """
    Abstract extension point for true downstream computer-vision benchmark evaluation.
    Enables comparing model inference/training on the full dataset vs the pruned dataset.
    """
    @abstractmethod
    def evaluate_downstream_task(
        self,
        original_video_path: str,
        optimized_video_path: str,
        task_type: str = "action_recognition"
    ) -> Dict[str, Any]:
        """
        Phase 2 implementation:
        1. Run PyTorch vision model on original video clips
        2. Run same PyTorch model on pruned/compressed video clips
        3. Measure accuracy delta (e.g. Top-1 Acc, Top-5 Acc, mAP, Latency)
        """
        pass

class PyTorchBenchmarkPhase2Stub(DownstreamMLBenchmark):
    """
    Architectural stub for Phase 2 PyTorch downstream benchmark.
    """
    def evaluate_downstream_task(
        self,
        original_video_path: str,
        optimized_video_path: str,
        task_type: str = "action_recognition"
    ) -> Dict[str, Any]:
        return {
            "status": "Phase 2 Extension Point",
            "model_architecture": "torchvision.models.video.r3d_18 (or VideoMAE / X3D)",
            "supported_metrics": ["top1_accuracy", "top5_accuracy", "mAP", "inference_latency_ms", "training_flops_saved"],
            "execution_mode": "Requires torch, torchvision, and labeled downstream action dataset.",
            "note": "Never claim downstream preservation without running this full evaluation pipeline."
        }
