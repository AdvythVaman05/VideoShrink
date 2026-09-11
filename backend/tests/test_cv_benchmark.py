import pytest
import json
from pathlib import Path
import numpy as np

from backend.app.evaluation.cv_benchmark import (
    BoundingBox,
    GroundTruthSequence,
    SyntheticGroundTruth,
    TrajectoryReconstructor,
    CVTaskEvaluator,
    DownstreamCVBenchmarkRunner,
)

def test_bounding_box_geometry_and_iou():
    box_a = BoundingBox(x=10.0, y=10.0, w=50.0, h=50.0)
    assert box_a.area == 2500.0
    assert box_a.centroid == (35.0, 35.0)

    # Identical box -> IoU = 1.0
    assert box_a.iou(box_a) == 1.0

    # Completely disjoint box -> IoU = 0.0
    box_b = BoundingBox(x=100.0, y=100.0, w=50.0, h=50.0)
    assert box_a.iou(box_b) == 0.0

    # Partial overlap:
    # box_a: [0, 0, 10, 10] (area 100)
    # box_c: [5, 0, 10, 10] (area 100)
    # Intersection: [5, 0, 5, 10] -> area 50
    # Union: 100 + 100 - 50 = 150
    # IoU: 50 / 150 = 1/3
    box_1 = BoundingBox(x=0.0, y=0.0, w=10.0, h=10.0)
    box_2 = BoundingBox(x=5.0, y=0.0, w=10.0, h=10.0)
    assert pytest.approx(box_1.iou(box_2), 0.001) == 1.0 / 3.0

def test_synthetic_ground_truth_generation():
    gt = SyntheticGroundTruth.generate(width=640, height=360, fps=30.0, duration_sec=10.0)
    assert gt.total_frames == 300
    assert gt.fps == 30.0
    assert len(gt.boxes) == 300
    assert gt.scene_cuts == [3.0, 6.0, 8.0]

    # Segment 1: Static Box
    b0 = gt.get_box_at(0)
    b89 = gt.get_box_at(89)
    assert b0.x == 240.0 and b0.y == 140.0 and b0.w == 160.0 and b0.h == 120.0
    assert b89.x == 240.0 and b89.y == 140.0

    # Segment 2: Moving Box (Linear Motion)
    b90 = gt.get_box_at(90)
    b150 = gt.get_box_at(150)
    assert b150.x > b90.x  # x coordinates move forward across the screen

    # Segment 4: Cooldown Box
    b299 = gt.get_box_at(299)
    assert b299.x == 260.0 and b299.y == 150.0 and b299.w == 120.0 and b299.h == 80.0

def test_dense_baseline_perfect_reconstruction():
    gt = SyntheticGroundTruth.generate(width=640, height=360, fps=30.0, duration_sec=10.0)
    dense_indices = list(range(gt.total_frames))

    metrics = CVTaskEvaluator.evaluate(
        ground_truth=gt,
        selected_indices=dense_indices,
        total_frames=gt.total_frames,
        fps=gt.fps
    )

    # Perfect retention when all frames are present
    assert pytest.approx(metrics.mean_iou, 0.0001) == 1.0
    assert pytest.approx(metrics.centroid_rmse_px, 0.0001) == 0.0
    assert pytest.approx(metrics.track_retention_ratio, 0.0001) == 1.0
    assert metrics.track_loss_rate_pct == 0.0
    assert metrics.frame_reduction_pct == 0.0
    assert metrics.frame_retention_pct == 100.0
    assert pytest.approx(metrics.scene_cut_latency_ms, 0.0001) == 0.0

def test_pruned_trajectory_reconstruction_behavior():
    gt = SyntheticGroundTruth.generate(width=640, height=360, fps=30.0, duration_sec=10.0)

    # Compare dense (30 fps) vs 10 fps vs 2 fps
    idx_30fps = list(range(0, 300, 1))
    idx_10fps = list(range(0, 300, 3))
    idx_2fps = list(range(0, 300, 15))

    m_30 = CVTaskEvaluator.evaluate(gt, idx_30fps, 300, 30.0)
    m_10 = CVTaskEvaluator.evaluate(gt, idx_10fps, 300, 30.0)
    m_2 = CVTaskEvaluator.evaluate(gt, idx_2fps, 300, 30.0)

    # Higher reduction should correspond to lower mIoU and higher RMSE during motion
    assert m_30.mean_iou > m_10.mean_iou > m_2.mean_iou
    assert m_30.centroid_rmse_px < m_10.centroid_rmse_px < m_2.centroid_rmse_px
    assert m_30.frame_reduction_pct < m_10.frame_reduction_pct < m_2.frame_reduction_pct

    # Bounded metrics
    assert 0.0 <= m_10.mean_iou <= 1.0
    assert 0.0 <= m_2.compression_accuracy_efficiency_score <= 1.0

def test_downstream_cv_benchmark_runner(tmp_path):
    sample_video = Path("sample_data/benchmark_sample.mp4")
    assert sample_video.exists(), "Sample benchmark video must exist"

    test_strategies = [
        {"name": "dense_baseline", "label": "Dense Baseline", "params": {}},
        {"name": "uniform", "label": "Uniform 10 FPS", "params": {"target_fps": 10.0}},
        {"name": "perceptual", "label": "Perceptual 0.95", "params": {"similarity_threshold": 0.95}},
        {"name": "motion_aware", "label": "Motion-Aware Adaptive", "params": {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0}},
    ]

    results = DownstreamCVBenchmarkRunner.run_benchmark(
        video_path=sample_video,
        strategies=test_strategies
    )

    assert len(results) == 4
    for r in results:
        assert "strategy" in r
        assert "mean_iou" in r
        assert "centroid_rmse_px" in r
        assert "track_retention_ratio" in r
        assert "frame_reduction_pct" in r
        assert "efficiency_score_caes" in r
        assert 0.0 <= r["mean_iou"] <= 1.0
        assert r["centroid_rmse_px"] >= 0.0

    # Check Dense Baseline row has perfect tracking retention
    dense_row = next(r for r in results if r["strategy"] == "dense_baseline")
    assert pytest.approx(dense_row["mean_iou"], 0.0001) == 1.0
    assert dense_row["frame_reduction_pct"] == 0.0

def test_dense_reference_tracker(tmp_path):
    sample_video = Path("sample_data/benchmark_sample.mp4")
    from backend.app.evaluation.cv_benchmark import DenseReferenceTracker
    ref_gt = DenseReferenceTracker.extract_dense_reference(sample_video)
    assert ref_gt.total_frames == 300
    assert len(ref_gt.boxes) == 300
    assert ref_gt.source == "dense_opencv_reference"
    for b in ref_gt.boxes[:10]:
        assert b.w > 0 and b.h > 0

def test_cv_benchmark_cli_execution(tmp_path):
    import subprocess
    out_json = tmp_path / "test_cv_results.json"
    out_csv = tmp_path / "test_cv_summary.csv"

    cmd = [
        "python", "experiments/run_cv_benchmark.py",
        "--video", "sample_data/benchmark_sample.mp4",
        "--output", str(out_json),
        "--csv", str(out_csv)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert out_json.exists()
    assert out_csv.exists()

    with open(out_json) as f:
        data = json.load(f)
        assert "benchmark_results" in data
        assert len(data["benchmark_results"]) >= 10
        assert "pareto_optimal_strategies" in data

def test_downstream_cv_benchmark_adapter():
    from backend.app.evaluation.cv_benchmark import DownstreamCVBenchmark
    bench = DownstreamCVBenchmark()
    res = bench.evaluate_downstream_task(
        original_video_path="sample_data/benchmark_sample.mp4",
        optimized_video_path="sample_data/benchmark_sample.mp4"
    )
    assert res["status"] == "Evaluated"
    assert res["original_frames"] == 300
    assert res["optimized_frames"] == 300
    assert "model_architecture" in res

def test_scene_cut_handling_when_no_cuts_present():
    from backend.app.evaluation.cv_benchmark import GroundTruthSequence, BoundingBox, CVTaskEvaluator
    gt_no_cuts = GroundTruthSequence(
        total_frames=10,
        fps=10.0,
        boxes=[BoundingBox(10, 10, 20, 20) for _ in range(10)],
        scene_cuts=[],
        source="dense_opencv_reference"
    )
    metrics = CVTaskEvaluator.evaluate(gt_no_cuts, [0, 5, 9], 10, 10.0)
    # When no scene cuts exist in ground truth, recall and latency must be None, not 1.0 and 0.0
    assert metrics.scene_cut_recall is None
    assert metrics.scene_cut_latency_ms is None
    d = metrics.to_dict()
    assert d["scene_cut_recall"] is None
    assert d["scene_cut_latency_ms"] is None



