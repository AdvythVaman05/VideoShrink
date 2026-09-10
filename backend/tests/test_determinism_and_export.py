import json
from pathlib import Path
from backend.app.video.reader import VideoReader
from backend.app.sampling.selector import FrameSelector
from backend.app.db.database import db
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
SAMPLE_VIDEO_PATH = Path("sample_data/benchmark_sample.mp4")

def test_sampling_determinism():
    reader = VideoReader(SAMPLE_VIDEO_PATH)

    # 1. Test uniform determinism
    res_u1 = FrameSelector.run_selection("uniform", reader, {"target_fps": 10.0})
    res_u2 = FrameSelector.run_selection("uniform", reader, {"target_fps": 10.0})
    assert res_u1.selected_indices == res_u2.selected_indices

    # 2. Test perceptual determinism
    res_p1 = FrameSelector.run_selection("perceptual", reader, {"similarity_threshold": 0.96})
    res_p2 = FrameSelector.run_selection("perceptual", reader, {"similarity_threshold": 0.96})
    assert res_p1.selected_indices == res_p2.selected_indices

    # 3. Test motion-aware determinism
    res_m1 = FrameSelector.run_selection("motion_aware", reader, {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0})
    res_m2 = FrameSelector.run_selection("motion_aware", reader, {"motion_sensitivity": 0.5, "min_fps": 2.0, "max_fps": 15.0})
    assert res_m1.selected_indices == res_m2.selected_indices

def test_experiment_export_json():
    # Insert a dummy experiment
    exp_id = db.create_experiment(
        video_filename="reproducibility_test.mp4",
        video_duration=10.0,
        strategy="motion_aware",
        parameters={"motion_sensitivity": 0.5},
        original_frames=300,
        selected_frames=120,
        retention_rate=0.40,
        reduction_rate=0.60,
        effective_fps=12.0,
        original_size_bytes=1000000,
        compressed_size_bytes=400000,
        file_size_reduction_pct=60.0,
        processing_time_sec=2.5,
        info_preservation_score=0.88,
        quality_summary={"mean_blur_score": 140.2, "blurry_frames_count": 2},
        failure_summary={"sensitive_segments_count": 1}
    )

    # Export via DB helper
    json_str = db.export_experiment_json(exp_id)
    assert json_str is not None
    data = json.loads(json_str)

    assert data["experiment_id"] == exp_id
    assert data["video_metadata"]["filename"] == "reproducibility_test.mp4"
    assert data["sampling_configuration"]["strategy"] == "motion_aware"
    assert data["results"]["selected_frames"] == 120
    assert data["results"]["retention_rate"] == 0.40
    assert "disclaimer" in data["evaluation_metrics"]
    assert "PROXY METRIC ONLY" in data["evaluation_metrics"]["disclaimer"]
    assert data["quality_metrics"]["mean_blur_score"] == 140.2

    # Export via API endpoint
    resp = client.get(f"/api/experiments/{exp_id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    api_data = resp.json()
    assert api_data["experiment_id"] == exp_id
