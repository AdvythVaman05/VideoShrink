import time
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.services.job_runner import job_runner
from backend.app.video.writer import VideoWriter, JobCancelledException
from backend.app.database.repositories import job_repo

client = TestClient(app)
SAMPLE_VIDEO_PATH = Path("sample_data/benchmark_sample.mp4")

def test_cancel_pending_job():
    """Verify a pending job transitions immediately to cancelled without starting."""
    job_id = job_runner.create_job(strategy_name="uniform")
    job = job_runner.get_job(job_id)
    assert job is not None
    assert job.status == "pending"

    res = job_runner.cancel_job(job_id)
    assert res["status"] == "cancelled"
    assert job.status == "cancelled"

    # Verify repository persistence
    doc = job_repo.get_job(job_id)
    assert doc is not None
    assert doc["status"] == "cancelled"
    assert doc.get("cancelled_at") is not None

def test_cancel_running_job_api_and_cleanup():
    """Verify cancelling an actively running job stops processing, removes output, and persists cancelled."""
    assert SAMPLE_VIDEO_PATH.exists()
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    assert upload_resp.status_code == 200
    video_id = upload_resp.json()["video_id"]

    # Start motion_aware processing with dense sampling so it takes several seconds
    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "motion_aware",
            "parameters": {"motion_threshold": 0.05, "min_interval": 1, "max_interval": 10},
            "generate_video": True
        }
    )
    assert proc_resp.status_code == 200
    job_id = proc_resp.json()["job_id"]

    # Brief delay to allow task to start executing
    time.sleep(0.05)

    # Cancel via API
    cancel_resp = client.post(f"/api/process/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] in ("cancelling", "cancelled")

    # Poll until terminal cancelled state (should be very fast, max 10s)
    max_wait = 10.0
    start = time.time()
    terminal_status = None
    while time.time() - start < max_wait:
        st_resp = client.get(f"/api/process/{job_id}/status")
        assert st_resp.status_code == 200
        st_data = st_resp.json()
        if st_data["status"] == "cancelled":
            terminal_status = st_data
            break
        time.sleep(0.1)

    assert terminal_status is not None, "Job did not reach cancelled state within timeout."
    assert terminal_status["status"] == "cancelled"

    # Verify no partial output video exists on disk
    partial_files = list(settings.PROCESSED_DIR.glob(f"optimized_{job_id}_*"))
    assert len(partial_files) == 0, f"Found unexpected partial files: {partial_files}"

    # Verify results endpoint rejects cancelled job with 400
    res_resp = client.get(f"/api/process/{job_id}/results")
    assert res_resp.status_code == 400
    assert "cancelled" in res_resp.json()["detail"].lower()

    # Verify download endpoint rejects cancelled job with 404
    dl_resp = client.get(f"/api/video/{job_id}/download")
    assert dl_resp.status_code == 404

    # Verify stream endpoint rejects cancelled job with 404
    stream_resp = client.get(f"/api/video/{job_id}/stream")
    assert stream_resp.status_code == 404

    # Verify repository document
    repo_doc = job_repo.get_job(job_id)
    assert repo_doc is not None
    assert repo_doc["status"] == "cancelled"
    assert repo_doc.get("cancelled_at") is not None

def test_cancel_unknown_job_404():
    """Verify cancelling an unknown job returns 404."""
    resp = client.post("/api/process/00000000-0000-0000-0000-000000000000/cancel")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

def test_cancel_completed_job_conflict_409():
    """Verify cancelling an already completed job returns 409 Conflict."""
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    video_id = upload_resp.json()["video_id"]

    # Run quick uniform job to completion
    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "uniform",
            "parameters": {"target_fps": 2.0},
            "generate_video": False
        }
    )
    job_id = proc_resp.json()["job_id"]

    # Wait for completion
    start = time.time()
    while time.time() - start < 15.0:
        st_resp = client.get(f"/api/process/{job_id}/status")
        if st_resp.json()["status"] == "completed":
            break
        time.sleep(0.1)

    assert client.get(f"/api/process/{job_id}/status").json()["status"] == "completed"

    # Attempt to cancel completed job
    cancel_resp = client.post(f"/api/process/{job_id}/cancel")
    assert cancel_resp.status_code == 409
    assert "cannot cancel completed job" in cancel_resp.json()["detail"].lower()

    # Status must remain completed
    assert client.get(f"/api/process/{job_id}/status").json()["status"] == "completed"

def test_cancel_idempotency():
    """Verify cancelling an already cancelled job returns 200 idempotently."""
    job_id = job_runner.create_job(strategy_name="uniform")
    job_runner.cancel_job(job_id)

    # First check status
    assert job_runner.get_job(job_id).status == "cancelled"

    # Second cancel request via API
    resp = client.post(f"/api/process/{job_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

def test_writer_cooperative_cancellation_and_cleanup(tmp_path):
    """Verify VideoWriter cleanly aborts and removes incomplete files when cancelled."""
    writer = VideoWriter()
    out_file = tmp_path / "test_cancel_output.mp4"

    call_count = 0
    def cancel_after_two_frames():
        nonlocal call_count
        call_count += 1
        return call_count >= 2

    # Should raise JobCancelledException
    try:
        writer.write_selected_frames(
            source_video_path=SAMPLE_VIDEO_PATH,
            selected_indices=list(range(0, 100)),
            output_video_path=out_file,
            cancellation_check=cancel_after_two_frames
        )
        assert False, "Expected JobCancelledException was not raised."
    except JobCancelledException:
        pass

    # Partial file must not remain on disk
    assert not out_file.exists(), "Incomplete output file was not cleaned up after cancellation."

def test_cancelled_job_never_becomes_completed():
    """Verify that once a job is cancelled, no background thread ever marks it completed."""
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    video_id = upload_resp.json()["video_id"]

    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "perceptual",
            "parameters": {"threshold": 0.99},
            "generate_video": True
        }
    )
    job_id = proc_resp.json()["job_id"]

    # Cancel immediately
    client.post(f"/api/process/{job_id}/cancel")

    # Wait 3 seconds
    time.sleep(3.0)

    job = job_runner.get_job(job_id)
    assert job is not None
    assert job.status == "cancelled"
    assert job.result is None

    repo_doc = job_repo.get_job(job_id)
    assert repo_doc["status"] == "cancelled"
    assert repo_doc.get("result") is None

def test_tab_inactivity_does_not_cancel_job():
    """Verify background job executes independently to completion without any polling."""
    with open(SAMPLE_VIDEO_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/upload",
            files={"file": ("benchmark_sample.mp4", f, "video/mp4")}
        )
    video_id = upload_resp.json()["video_id"]

    proc_resp = client.post(
        "/api/process",
        json={
            "video_id": video_id,
            "strategy": "uniform",
            "parameters": {"target_fps": 5.0},
            "generate_video": False
        }
    )
    job_id = proc_resp.json()["job_id"]

    # Simulate client switching tabs for 3 seconds without polling
    time.sleep(3.0)

    # Client returns and checks status: job should NOT be cancelled
    st_resp = client.get(f"/api/process/{job_id}/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["status"] in ("processing", "completed")
    assert st_data["status"] != "cancelled"
