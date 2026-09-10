"""
Production smoke test for VideoShrink.
Verifies the complete lifecycle:
1. Health check & OpenAPI documentation
2. Video upload (benchmark_sample.mp4)
3. Metadata inspection
4. Asynchronous motion-aware processing & job status polling
5. Full results extraction (reduction rate, proxy metrics, failure diagnostics)
6. Stream and download validation with OpenCV playability check
7. SQLite experiment persistence and JSON export verification
"""

import sys
import time
import json
from pathlib import Path
import cv2
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_VIDEO_PATH = BASE_DIR / "sample_data" / "benchmark_sample.mp4"

def run_smoke_test(base_url: str = "http://127.0.0.1:8000"):
    print(f"\n=======================================================")
    print(f"Running Production Smoke Test against {base_url}")
    print(f"=======================================================")

    if not SAMPLE_VIDEO_PATH.exists():
        raise FileNotFoundError(f"Sample video not found at {SAMPLE_VIDEO_PATH}")

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # 1. Health check
        print("1. Testing /health endpoint...")
        resp = client.get("/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Unexpected health response: {data}"
        print(f"   [PASS] Health check returned: {data}")

        # 2. OpenAPI documentation check
        print("2. Testing /docs OpenAPI endpoint...")
        resp = client.get("/docs")
        assert resp.status_code == 200, f"Docs check failed: {resp.status_code}"
        print("   [PASS] /docs accessible")

        # 3. Video Upload
        print(f"3. Uploading {SAMPLE_VIDEO_PATH.name}...")
        with open(SAMPLE_VIDEO_PATH, "rb") as f:
            files = {"file": (SAMPLE_VIDEO_PATH.name, f, "video/mp4")}
            resp = client.post("/api/upload", files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text}"
        upload_data = resp.json()
        video_id = upload_data["video_id"]
        meta = upload_data["metadata"]
        print(f"   [PASS] Upload successful. Video ID: {video_id}")
        print(f"   Metadata: {meta['width']}x{meta['height']}, {meta['fps']} FPS, {meta['total_frames']} frames")
        assert meta["total_frames"] == 300, f"Expected 300 frames, got {meta['total_frames']}"

        # 4. Metadata verification
        print("4. Fetching metadata via /api/video/{video_id}/metadata...")
        resp = client.get(f"/api/video/{video_id}/metadata")
        assert resp.status_code == 200, f"Metadata request failed: {resp.status_code} {resp.text}"
        fetched_meta = resp.json()
        assert fetched_meta["width"] == 640 and fetched_meta["height"] == 360
        assert fetched_meta["fps"] == 30.0
        assert fetched_meta["total_frames"] == 300
        print("   [PASS] Metadata endpoint accurately returned 640x360, 30 FPS, 300 frames")

        # 5. Background Processing
        print("5. Launching Motion-Aware compression job...")
        payload = {
            "video_id": video_id,
            "strategy": "motion_aware",
            "parameters": {
                "motion_sensitivity": 0.5,
                "min_fps": 2.0,
                "max_fps": 15.0,
            }
        }
        resp = client.post("/api/process", json=payload)
        assert resp.status_code == 200, f"Process submission failed: {resp.status_code} {resp.text}"
        job_id = resp.json()["job_id"]
        print(f"   [PASS] Job submitted. Job ID: {job_id}")

        # 6. Poll Job Status
        print("6. Polling job status via /api/process/{job_id}/status...")
        start_time = time.time()
        completed = False
        while time.time() - start_time < 60.0:
            resp = client.get(f"/api/process/{job_id}/status")
            assert resp.status_code == 200
            status_data = resp.json()
            status = status_data["status"]
            progress = status_data.get("progress", 0)
            current_step = status_data.get("current_step", "")
            print(f"   Progress: {progress:.1f}% - {current_step}")
            if status == "completed":
                completed = True
                break
            elif status == "failed":
                raise RuntimeError(f"Job failed: {status_data.get('error_message')}")
            time.sleep(0.5)

        assert completed, "Job did not complete within timeout"
        print("   [PASS] Job completed successfully")

        # 7. Retrieve Results
        print("7. Retrieving job results from /api/process/{job_id}/results...")
        resp = client.get(f"/api/process/{job_id}/results")
        assert resp.status_code == 200, f"Results fetch failed: {resp.status_code} {resp.text}"
        results = resp.json()

        metrics = results["metrics"]
        bench = results["benchmark"]
        failures = results.get("failure_analysis", {}).get("segments", [])

        print(f"   Original Frames: {metrics['original_frames']}")
        print(f"   Selected Frames: {metrics['selected_frames']}")
        print(f"   Frame Reduction: {metrics['frame_reduction_pct']:.1f}%")
        print(f"   File Size Reduction: {metrics['file_size_reduction_pct']:.1f}%")
        print(f"   Effective FPS: {metrics['effective_fps']:.1f}")
        print(f"   Proxy Fidelity Score: {bench.get('proxy_fidelity_score', 0):.1f}%")
        print(f"   Sensitive Segments Flagged: {len(failures)}")

        assert metrics["frame_reduction_pct"] > 50.0, "Expected >50% frame reduction"
        assert metrics["file_size_reduction_pct"] > 50.0, "Expected >50% file size reduction"
        assert "PROXY METRIC ONLY" in bench.get("disclaimer", ""), "Proxy metric disclaimer must be present"
        print("   [PASS] Metrics and disclaimers validated")

        # 8. Video Streaming and Download Check
        print("8. Testing /api/video/{job_id}/stream and download endpoints...")
        stream_resp = client.get(f"/api/video/{job_id}/stream")
        assert stream_resp.status_code in [200, 206], f"Stream failed: {stream_resp.status_code}"
        assert len(stream_resp.content) > 10000, "Streamed content too small"

        download_resp = client.get(f"/api/video/{job_id}/download")
        assert download_resp.status_code == 200
        download_bytes = download_resp.content
        assert len(download_bytes) > 10000, "Downloaded video too small"

        # Validate with OpenCV
        temp_out = BASE_DIR / "data" / "processed" / f"smoke_test_verify_{job_id[:8]}.mp4"
        with open(temp_out, "wb") as f:
            f.write(download_bytes)

        cap = cv2.VideoCapture(str(temp_out))
        assert cap.isOpened(), "Downloaded video could not be opened by OpenCV"
        dec_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dec_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        dec_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        temp_out.unlink(missing_ok=True)

        print(f"   [PASS] Video file valid and decoded: {dec_w}x{dec_h}, {dec_frames} frames")

        # 9. SQLite Experiment Persistence & Export Check
        print("9. Verifying SQLite experiment persistence & export...")
        exp_resp = client.get("/api/experiments")
        assert exp_resp.status_code == 200
        exp_list = exp_resp.json()
        assert len(exp_list) > 0, "No experiments found in database"
        latest_exp = exp_list[0]
        exp_id = latest_exp["id"]
        print(f"   Found latest experiment: {latest_exp['experiment_code']} ({exp_id})")

        export_resp = client.get(f"/api/experiments/{exp_id}/export")
        assert export_resp.status_code == 200
        exp_export = export_resp.json()
        assert exp_export["experiment_id"] == exp_id
        assert "video_metadata" in exp_export
        assert "sampling_configuration" in exp_export
        assert "results" in exp_export
        assert "evaluation_metrics" in exp_export
        print("   [PASS] SQLite persistence and JSON export verified")

    print("\n=======================================================")
    print("ALL PRODUCTION SMOKE TESTS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    run_smoke_test(url)
