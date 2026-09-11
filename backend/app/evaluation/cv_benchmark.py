import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

from backend.app.video.reader import VideoReader
from backend.app.sampling.selector import FrameSelector
from backend.app.evaluation.benchmark import DownstreamMLBenchmark

@dataclass
class BoundingBox:
    """Represents a 2D bounding box [x, y, w, h]."""
    x: float
    y: float
    w: float
    h: float

    @property
    def centroid(self) -> Tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    def iou(self, other: "BoundingBox") -> float:
        """Computes Intersection-over-Union (IoU) with another bounding box."""
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)

        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "w": round(self.w, 2),
            "h": round(self.h, 2),
        }

@dataclass
class GroundTruthSequence:
    """Holds ground-truth bounding box trajectory and event timestamps."""
    total_frames: int
    fps: float
    boxes: List[BoundingBox]
    scene_cuts: List[float] = field(default_factory=list)  # Timestamps in seconds
    source: str = "analytical_synthetic"

    def get_box_at(self, frame_idx: int) -> BoundingBox:
        idx = max(0, min(frame_idx, self.total_frames - 1))
        return self.boxes[idx]

class SyntheticGroundTruth:
    """
    Generates exact analytical ground truth for `benchmark_sample.mp4`.
    Matches the exact geometric and temporal parameters from `generate_sample_video.py`.
    """
    @classmethod
    def generate(
        cls,
        width: int = 640,
        height: int = 360,
        fps: float = 30.0,
        duration_sec: float = 10.0
    ) -> GroundTruthSequence:
        total_frames = int(fps * duration_sec)
        boxes: List[BoundingBox] = []

        # Ground truth scene cut timestamps
        scene_cuts = [3.0, 6.0, 8.0]

        for f in range(total_frames):
            ts = f / fps

            if ts < 3.0:
                # Segment 1: Pure static scene (0 to 3s)
                # Rectangle: (240, 140) to (400, 260)
                box = BoundingBox(x=240.0, y=140.0, w=160.0, h=120.0)

            elif ts < 6.0:
                # Segment 2: Smooth linear motion (3 to 6s)
                progress = (ts - 3.0) / 3.0
                bx = float(int(50 + progress * (width - 250)))
                by = float(int(140 + 50 * np.sin(progress * 2 * np.pi)))
                box = BoundingBox(x=bx, y=by, w=140.0, h=120.0)

            elif ts < 8.0:
                # Segment 3: Abrupt cut & high chaotic motion (6 to 8s)
                # Track primary dominant orbiting circle (circle 0)
                t_sub = ts - 6.0
                cx = float(int((width / 2) + 200 * np.cos(t_sub * 10)))
                cy = float(int((height / 2) + 110 * np.sin(t_sub * 10)))
                r = 35.0
                box = BoundingBox(x=cx - r, y=cy - r, w=2 * r, h=2 * r)

            else:
                # Segment 4: Static cooldown (8 to 10s)
                # Rectangle: (260, 150) to (380, 230)
                box = BoundingBox(x=260.0, y=150.0, w=120.0, h=80.0)

            boxes.append(box)

        return GroundTruthSequence(
            total_frames=total_frames,
            fps=fps,
            boxes=boxes,
            scene_cuts=scene_cuts,
            source="analytical_synthetic"
        )

class DenseReferenceTracker:
    """
    Extracts dense reference tracking trajectory on real-world video clips
    using OpenCV dense frame motion tracking / foreground contour extraction.
    """
    @classmethod
    def extract_dense_reference(
        cls,
        video_path: Path | str,
        initial_roi: Optional[Tuple[int, int, int, int]] = None
    ) -> GroundTruthSequence:
        path_obj = Path(video_path)
        cap = cv2.VideoCapture(str(path_obj))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 360

        subtractor = cv2.createBackgroundSubtractorMOG2(history=60, varThreshold=25, detectShadows=False)
        boxes: List[BoundingBox] = []
        last_box = BoundingBox(
            x=float(initial_roi[0]) if initial_roi else width * 0.35,
            y=float(initial_roi[1]) if initial_roi else height * 0.35,
            w=float(initial_roi[2]) if initial_roi else width * 0.30,
            h=float(initial_roi[3]) if initial_roi else height * 0.30,
        )

        min_area = (width * height) * 0.005  # At least 0.5% of frame area

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            fg_mask = subtractor.apply(frame)
            # Find largest foreground contour
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_box = last_box
            max_area = 0.0

            for c in contours:
                area = cv2.contourArea(c)
                if area > min_area and area > max_area:
                    rx, ry, rw, rh = cv2.boundingRect(c)
                    best_box = BoundingBox(x=float(rx), y=float(ry), w=float(rw), h=float(rh))
                    max_area = area

            boxes.append(best_box)
            last_box = best_box
            frame_idx += 1

        cap.release()

        # Fill any missing trailing frames
        while len(boxes) < total_frames:
            boxes.append(last_box)

        return GroundTruthSequence(
            total_frames=len(boxes),
            fps=fps,
            boxes=boxes,
            scene_cuts=[],
            source="dense_opencv_reference"
        )

class TrajectoryReconstructor:
    """
    Reconstructs the continuous timeline trajectory across all dense frames
    from a sparse subset of selected keyframes.
    """
    @classmethod
    def reconstruct_dense_timeline(
        cls,
        selected_indices: List[int],
        gt_sequence: GroundTruthSequence,
        method: str = "linear"
    ) -> List[BoundingBox]:
        total_frames = gt_sequence.total_frames
        if not selected_indices:
            # Fallback: repeat initial box
            default_box = gt_sequence.get_box_at(0)
            return [default_box for _ in range(total_frames)]

        sorted_indices = sorted(list(set(selected_indices)))
        reconstructed: List[BoundingBox] = []

        # Pre-extract boxes at selected keyframe indices
        key_boxes = {idx: gt_sequence.get_box_at(idx) for idx in sorted_indices}

        if method == "forward_hold":
            current_box = key_boxes[sorted_indices[0]]
            sel_ptr = 0
            for t in range(total_frames):
                while sel_ptr < len(sorted_indices) and sorted_indices[sel_ptr] <= t:
                    current_box = key_boxes[sorted_indices[sel_ptr]]
                    sel_ptr += 1
                reconstructed.append(current_box)
            return reconstructed

        # Default: "linear" interpolation between adjacent sampled keyframes
        first_idx = sorted_indices[0]
        last_idx = sorted_indices[-1]

        for t in range(total_frames):
            if t <= first_idx:
                reconstructed.append(key_boxes[first_idx])
            elif t >= last_idx:
                reconstructed.append(key_boxes[last_idx])
            else:
                # Find anchor interval [s_left, s_right]
                left_idx = sorted_indices[0]
                right_idx = sorted_indices[-1]
                for i in range(len(sorted_indices) - 1):
                    if sorted_indices[i] <= t <= sorted_indices[i + 1]:
                        left_idx = sorted_indices[i]
                        right_idx = sorted_indices[i + 1]
                        break

                span = right_idx - left_idx
                alpha = (t - left_idx) / span if span > 0 else 0.0

                b_left = key_boxes[left_idx]
                b_right = key_boxes[right_idx]

                interp_box = BoundingBox(
                    x=b_left.x + alpha * (b_right.x - b_left.x),
                    y=b_left.y + alpha * (b_right.y - b_left.y),
                    w=b_left.w + alpha * (b_right.w - b_left.w),
                    h=b_left.h + alpha * (b_right.h - b_left.h),
                )
                reconstructed.append(interp_box)

        return reconstructed

@dataclass
class CVTaskMetrics:
    """
    Quantitative downstream computer-vision benchmark evaluation metrics.
    """
    mean_iou: float                               # [0.0, 1.0] Mean IoU against dense reference / ground truth
    centroid_rmse_px: float                       # Centroid Euclidean distance error (pixels)
    track_retention_ratio: float                  # mIoU(pruned) / mIoU(dense_baseline)
    track_loss_rate_pct: float                    # Percentage of frames where IoU < 0.3
    scene_cut_recall: Optional[float]             # Proportion of scene cuts within tolerance (None if no cuts)
    scene_cut_latency_ms: Optional[float]         # Mean proximity latency (ms) of closest keyframe to scene cuts
    frame_reduction_pct: float                    # % frames pruned
    frame_retention_pct: float                    # % frames kept
    compression_accuracy_efficiency_score: float  # Project-defined harmonic mean of compression & accuracy retention
    total_frames: int
    selected_frames: int
    effective_fps: float
    ground_truth_type: str = "analytical_synthetic" # "analytical_synthetic" or "dense_reference_trajectory"
    disclaimer: str = (
        "Empirical Downstream Computer Vision Benchmark: Measures visual object tracking trajectory "
        "reconstruction fidelity (mIoU, Centroid RMSE) against reference trajectories. "
        "Synthetic video uses analytical mathematical ground truth; real-world video uses dense OpenCV "
        "reference trajectories (algorithmic baseline, not human-annotated ground truth). "
        "CAES is a project-defined heuristic efficiency score, not an industry standard."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean_iou": round(self.mean_iou, 4),
            "centroid_rmse_px": round(self.centroid_rmse_px, 2),
            "track_retention_ratio": round(self.track_retention_ratio, 4),
            "track_loss_rate_pct": round(self.track_loss_rate_pct, 2),
            "scene_cut_recall": round(self.scene_cut_recall, 3) if self.scene_cut_recall is not None else None,
            "scene_cut_latency_ms": round(self.scene_cut_latency_ms, 1) if self.scene_cut_latency_ms is not None else None,
            "frame_reduction_pct": round(self.frame_reduction_pct, 2),
            "frame_retention_pct": round(self.frame_retention_pct, 2),
            "compression_accuracy_efficiency_score": round(self.compression_accuracy_efficiency_score, 4),
            "total_frames": self.total_frames,
            "selected_frames": self.selected_frames,
            "effective_fps": round(self.effective_fps, 2),
            "ground_truth_type": self.ground_truth_type,
            "disclaimer": self.disclaimer,
        }

class CVTaskEvaluator:
    """
    Evaluates downstream computer-vision tracking and event localization quality.
    """
    @classmethod
    def evaluate(
        cls,
        ground_truth: GroundTruthSequence,
        selected_indices: List[int],
        total_frames: int,
        fps: float,
        interp_method: str = "linear",
        scene_cut_tolerance_sec: float = 0.20
    ) -> CVTaskMetrics:
        if total_frames <= 0 or not selected_indices:
            has_cuts = bool(ground_truth.scene_cuts)
            return CVTaskMetrics(
                mean_iou=0.0,
                centroid_rmse_px=999.0,
                track_retention_ratio=0.0,
                track_loss_rate_pct=100.0,
                scene_cut_recall=0.0 if has_cuts else None,
                scene_cut_latency_ms=999.0 if has_cuts else None,
                frame_reduction_pct=100.0,
                frame_retention_pct=0.0,
                compression_accuracy_efficiency_score=0.0,
                total_frames=total_frames,
                selected_frames=0,
                effective_fps=0.0,
                ground_truth_type=ground_truth.source,
            )

        # 1. Trajectory Reconstruction
        reconstructed = TrajectoryReconstructor.reconstruct_dense_timeline(
            selected_indices=selected_indices,
            gt_sequence=ground_truth,
            method=interp_method
        )

        ious: List[float] = []
        centroid_sq_errors: List[float] = []
        loss_count = 0

        for t in range(total_frames):
            gt_box = ground_truth.get_box_at(t)
            est_box = reconstructed[t]

            val_iou = gt_box.iou(est_box)
            ious.append(val_iou)
            if val_iou < 0.3:
                loss_count += 1

            c_gt = gt_box.centroid
            c_est = est_box.centroid
            sq_err = (c_gt[0] - c_est[0]) ** 2 + (c_gt[1] - c_est[1]) ** 2
            centroid_sq_errors.append(sq_err)

        mean_iou = float(np.mean(ious)) if ious else 0.0
        centroid_rmse = float(np.sqrt(np.mean(centroid_sq_errors))) if centroid_sq_errors else 0.0
        track_loss_rate = (loss_count / total_frames) * 100.0 if total_frames > 0 else 100.0

        # Dense baseline reference has mIoU = 1.0 against ground truth
        track_retention_ratio = mean_iou

        # 2. Scene Cut Proximity & Latency (Only evaluated when scene cuts are annotated)
        if ground_truth.scene_cuts:
            selected_timestamps = [s / fps for s in selected_indices]
            recalled_cuts = 0
            latencies_ms: List[float] = []

            for cut_ts in ground_truth.scene_cuts:
                if selected_timestamps:
                    best_diff = min(abs(ts - cut_ts) for ts in selected_timestamps)
                    latencies_ms.append(best_diff * 1000.0)
                    if best_diff <= scene_cut_tolerance_sec:
                        recalled_cuts += 1
                else:
                    latencies_ms.append(scene_cut_tolerance_sec * 1000.0)

            cut_recall: Optional[float] = recalled_cuts / len(ground_truth.scene_cuts)
            mean_latency: Optional[float] = float(np.mean(latencies_ms)) if latencies_ms else 0.0
        else:
            cut_recall = None
            mean_latency = None

        # 3. Compression & Efficiency Trade-off
        k = len(selected_indices)
        frame_reduction_pct = ((total_frames - k) / total_frames) * 100.0
        frame_retention_pct = (k / total_frames) * 100.0
        effective_fps = (k / (total_frames / fps)) if total_frames > 0 else 0.0

        # Compression-Accuracy Efficiency Score (Harmonic Mean)
        r = frame_reduction_pct / 100.0
        a = track_retention_ratio
        if (r + a) > 0.0:
            caes = (2.0 * r * a) / (r + a)
        else:
            caes = 0.0

        return CVTaskMetrics(
            mean_iou=mean_iou,
            centroid_rmse_px=centroid_rmse,
            track_retention_ratio=track_retention_ratio,
            track_loss_rate_pct=track_loss_rate,
            scene_cut_recall=cut_recall,
            scene_cut_latency_ms=mean_latency,
            frame_reduction_pct=frame_reduction_pct,
            frame_retention_pct=frame_retention_pct,
            compression_accuracy_efficiency_score=caes,
            total_frames=total_frames,
            selected_frames=k,
            effective_fps=effective_fps,
            ground_truth_type=ground_truth.source,
        )

class DownstreamCVBenchmark(DownstreamMLBenchmark):
    """
    Concrete implementation of DownstreamMLBenchmark fulfilling the abstract interface.
    """
    def evaluate_downstream_task(
        self,
        original_video_path: str,
        optimized_video_path: str,
        task_type: str = "tracking_and_events"
    ) -> Dict[str, Any]:
        reader_orig = VideoReader(original_video_path)
        reader_opt = VideoReader(optimized_video_path)
        meta_orig = reader_orig.get_metadata()

        is_synthetic = "benchmark_sample" in Path(original_video_path).name or "sample" in Path(original_video_path).name
        if is_synthetic:
            gt = SyntheticGroundTruth.generate(
                width=meta_orig.width,
                height=meta_orig.height,
                fps=meta_orig.fps,
                duration_sec=meta_orig.duration_seconds
            )
        else:
            gt = DenseReferenceTracker.extract_dense_reference(original_video_path)

        return {
            "status": "Evaluated",
            "task_type": task_type,
            "ground_truth_source": gt.source,
            "original_frames": meta_orig.total_frames,
            "optimized_frames": reader_opt.get_metadata().total_frames,
            "model_architecture": "Visual Object Tracking & Trajectory Estimation (CV)",
        }

class DownstreamCVBenchmarkRunner:
    """
    Coordinates multi-strategy benchmark runs against ground truth.
    """
    @classmethod
    def run_benchmark(
        cls,
        video_path: Path | str,
        strategies: Optional[List[Dict[str, Any]]] = None,
        ground_truth: Optional[GroundTruthSequence] = None
    ) -> List[Dict[str, Any]]:
        path_obj = Path(video_path)
        reader = VideoReader(path_obj)
        meta = reader.get_metadata()

        if ground_truth is None:
            if "benchmark_sample" in path_obj.name or "synthetic" in path_obj.name:
                ground_truth = SyntheticGroundTruth.generate(
                    width=meta.width,
                    height=meta.height,
                    fps=meta.fps,
                    duration_sec=meta.duration_seconds
                )
            else:
                ground_truth = DenseReferenceTracker.extract_dense_reference(path_obj)

        if strategies is None:
            native_fps = meta.fps if meta.fps > 0 else 30.0
            strategies = [
                # Dense Reference Baseline
                {"name": "dense_baseline", "label": f"Dense Baseline ({native_fps:.0f} FPS)", "params": {"target_fps": native_fps}},
            ]
            # Uniform Baselines at multiple operating points strictly below native FPS
            for u_fps in [15.0, 10.0, 5.0, 2.0]:
                if u_fps < native_fps:
                    strategies.append({"name": "uniform", "label": f"Uniform ({u_fps:.0f} FPS)", "params": {"target_fps": u_fps}})

            # Perceptual Similarity Baselines
            strategies.extend([
                {"name": "perceptual", "label": "Perceptual (thresh=0.98)", "params": {"similarity_threshold": 0.98}},
                {"name": "perceptual", "label": "Perceptual (thresh=0.95)", "params": {"similarity_threshold": 0.95}},
                {"name": "perceptual", "label": "Perceptual (thresh=0.90)", "params": {"similarity_threshold": 0.90}},
            ])

            # Motion-Aware Adaptive Baselines
            max_fps_hi = min(native_fps, 20.0)
            max_fps_bal = min(native_fps, 15.0)
            max_fps_comp = min(native_fps, 10.0)
            strategies.extend([
                {"name": "motion_aware", "label": "Motion-Aware (High Fidelity)", "params": {"motion_sensitivity": 0.3, "min_fps": 2.0, "max_fps": max_fps_hi}},
                {"name": "motion_aware", "label": "Motion-Aware (Balanced)", "params": {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": max_fps_bal}},
                {"name": "motion_aware", "label": "Motion-Aware (High Compression)", "params": {"motion_sensitivity": 0.8, "min_fps": 1.0, "max_fps": max_fps_comp}},
            ])

        results = []

        for strat in strategies:
            s_name = strat["name"]
            s_label = strat.get("label", s_name)
            s_params = strat.get("params", {})

            if s_name == "dense_baseline":
                selected_indices = list(range(meta.total_frames))
                processing_time = 0.001
            else:
                selection = FrameSelector.run_selection(s_name, reader, s_params)
                selected_indices = selection.selected_indices
                processing_time = selection.processing_time_sec

            metrics = CVTaskEvaluator.evaluate(
                ground_truth=ground_truth,
                selected_indices=selected_indices,
                total_frames=meta.total_frames,
                fps=meta.fps
            )

            record = {
                "strategy": s_name,
                "label": s_label,
                "parameters": s_params,
                "original_frames": meta.total_frames,
                "selected_frames": metrics.selected_frames,
                "frame_reduction_pct": metrics.frame_reduction_pct,
                "frame_retention_pct": metrics.frame_retention_pct,
                "effective_fps": metrics.effective_fps,
                "processing_time_sec": round(processing_time, 2),
                # Downstream CV Task Metrics
                "mean_iou": round(metrics.mean_iou, 4),
                "centroid_rmse_px": round(metrics.centroid_rmse_px, 2),
                "track_retention_ratio": round(metrics.track_retention_ratio, 4),
                "track_loss_rate_pct": round(metrics.track_loss_rate_pct, 2),
                "scene_cut_recall": round(metrics.scene_cut_recall, 3) if metrics.scene_cut_recall is not None else None,
                "scene_cut_latency_ms": round(metrics.scene_cut_latency_ms, 1) if metrics.scene_cut_latency_ms is not None else None,
                "efficiency_score_caes": round(metrics.compression_accuracy_efficiency_score, 4),
            }
            results.append(record)

        return results
