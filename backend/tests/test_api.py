import time
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
SAMPLE_VIDEO_PATH = Path("sample_data/benchmark_sample.mp4")

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "mongodb" in data

def test_upload_and_metadata():
    assert SAMPLE_VIDEO_PATH.exists()
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "video_id" in data
    assert data["filename"] == "benchmark_sample.mp4"
    assert data["metadata"]["total_frames"] == 300

    video_id = data["video_id"]

    # Test metadata get
    meta_resp = client.get(f"/api/video/{video_id}/metadata")
    assert meta_resp.status_code == 200
    assert meta_resp.json()["total_frames"] == 300

def test_process_and_poll_results():
    # 1. Upload
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    video_id = upload_resp.json()["video_id"]

    # 2. Start process
    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "uniform",
            "parameters": {"target_fps": 10.0},
            "generate_video": True
        }
    )
    assert proc_resp.status_code == 200
    job_id = proc_resp.json()["job_id"]

    # 3. Poll status until completed (timeout 30s)
    max_wait = 30
    start = time.time()
    completed = False

    while time.time() - start < max_wait:
        status_resp = client.get(f"/api/process/{job_id}/status")
        assert status_resp.status_code == 200
        st = status_resp.json()
        if st["status"] == "completed":
            completed = True
            break
        elif st["status"] == "failed":
            assert False, f"Job failed: {st.get('error_message')}"
        time.sleep(0.5)

    assert completed, "Processing job timed out."

    # 4. Check results
    res_resp = client.get(f"/api/process/{job_id}/results")
    assert res_resp.status_code == 200
    result = res_resp.json()

    assert result["strategy"] == "uniform"
    assert result["metrics"]["original_frames"] == 300
    assert result["metrics"]["selected_frames"] < 300
    assert result["output_video"]["exists"] is True
    assert len(result["preview_frames"]) > 0

    # 5. Check experiment history
    exp_resp = client.get("/api/experiments")
    assert exp_resp.status_code == 200
    experiments = exp_resp.json()
    assert len(experiments) > 0
    assert any(e["video_filename"] == "benchmark_sample.mp4" for e in experiments)

def test_compare_endpoint():
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    video_id = upload_resp.json()["video_id"]

    compare_resp = client.post(
        "/api/compare",
        json={"video_id": video_id}
    )
    assert compare_resp.status_code == 200
    comp_data = compare_resp.json()
    assert "comparison" in comp_data
    assert len(comp_data["comparison"]) == 3
    strat_names = [c["strategy"] for c in comp_data["comparison"]]
    assert "uniform" in strat_names
    assert "perceptual" in strat_names
    assert "motion_aware" in strat_names

def test_job_background_independence_and_recovery():
    """
    Test that background jobs continue processing independently even when
    the client disconnects / stops polling, and that returning later
    successfully recovers the completed results and output video.
    """
    # 1. Upload video
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    assert upload_resp.status_code == 200
    video_id = upload_resp.json()["video_id"]

    # 2. Trigger background processing
    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "perceptual",
            "parameters": {"threshold": 0.2},
            "generate_video": True
        }
    )
    assert proc_resp.status_code == 200
    job_id = proc_resp.json()["job_id"]

    # 3. Simulate inactive tab / zero polling for 3 seconds
    # The client completely ceases HTTP requests while server executes in background thread
    time.sleep(3.0)

    # 4. Client returns and polls status
    status_resp = client.get(f"/api/process/{job_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] in ["processing", "completed"]

    # If not yet completed, wait briefly for completion
    if status_data["status"] != "completed":
        for _ in range(30):
            time.sleep(0.5)
            s = client.get(f"/api/process/{job_id}/status").json()
            if s["status"] == "completed":
                break

    # 5. Retrieve final results
    results_resp = client.get(f"/api/process/{job_id}/results")
    assert results_resp.status_code == 200
    res = results_resp.json()
    assert res["job_id"] == job_id
    assert res["metrics"]["original_frames"] == 300
    assert res["output_video"]["exists"] is True

    # 6. Verify download and stream endpoints work for recovered job
    dl_resp = client.get(f"/api/process/{job_id}/download")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 1000

    stream_resp = client.get(f"/api/process/{job_id}/stream")
    assert stream_resp.status_code == 200

    # 7. Stale / nonexistent job ID returns 404
    stale_resp = client.get("/api/process/nonexistent-stale-uuid-12345/status")
    assert stale_resp.status_code == 404
