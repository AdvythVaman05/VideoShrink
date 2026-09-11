import pytest
from backend.app.database.mongodb import mask_mongo_uri, MongoDBManager, mongo_manager
from backend.app.database.repositories import (
    VideoRepository,
    JobRepository,
    ExperimentRepository,
    video_repo,
    job_repo,
    experiment_repo,
)
from backend.app.services.job_runner import job_runner

def test_mask_mongo_uri():
    uri = "mongodb+srv://admin_user:SuperSecretPassword123@cluster0.abc.mongodb.net/videoshrink?retryWrites=true&w=majority"
    masked = mask_mongo_uri(uri)
    assert "SuperSecretPassword123" not in masked
    assert "admin_user:***@" in masked
    assert mask_mongo_uri(None) == "None"
    assert mask_mongo_uri("") == "None"

def test_mongodb_manager_singleton_and_health():
    mgr1 = MongoDBManager()
    mgr2 = MongoDBManager()
    assert mgr1 is mgr2

    health = mgr1.check_health()
    assert "status" in health
    # When MONGODB_URI is unset in local test environment
    if not mgr1.is_configured:
        assert health["status"] == "not_configured"
        assert health["fallback_mode"] is True

def test_video_repository_offline_mode():
    test_video_id = "test-video-uuid-123"
    meta = {
        "filename": "test.mp4",
        "duration_seconds": 12.5,
        "total_frames": 375,
        "width": 1920,
        "height": 1080,
    }
    video_repo.create_video(
        video_id=test_video_id,
        filename="test.mp4",
        filepath="/data/uploads/test.mp4",
        file_size_bytes=1048576,
        metadata=meta,
    )

    doc = video_repo.get_video(test_video_id)
    assert doc is not None
    assert doc["video_id"] == test_video_id
    assert doc["filename"] == "test.mp4"
    assert doc["metadata"]["total_frames"] == 375

def test_job_repository_and_recovery():
    test_job_id = "test-job-uuid-456"
    test_video_id = "test-video-uuid-123"

    job_repo.create_job(
        job_id=test_job_id,
        video_id=test_video_id,
        strategy_name="perceptual",
        strategy_params={"similarity_threshold": 0.95},
    )

    jdoc = job_repo.get_job(test_job_id)
    assert jdoc is not None
    assert jdoc["status"] == "pending"
    assert jdoc["progress"] == 0.0

    job_repo.update_progress(test_job_id, 45.0, "Sampling frames...")
    jdoc2 = job_repo.get_job(test_job_id)
    assert jdoc2["progress"] == 45.0
    assert jdoc2["current_step"] == "Sampling frames..."

    # Test job recovery in job_runner when cleared from memory
    job_runner.jobs.pop(test_job_id, None)
    assert test_job_id not in job_runner.jobs

    recovered = job_runner.get_job(test_job_id)
    assert recovered is not None
    assert recovered.job_id == test_job_id
    assert recovered.progress == 45.0
    assert recovered.current_step == "Sampling frames..."

    # Test complete
    job_repo.complete_job(
        job_id=test_job_id,
        result={"summary": "ok"},
        processing_time_sec=1.5,
    )
    jdoc3 = job_repo.get_job(test_job_id)
    assert jdoc3["status"] == "completed"
    assert jdoc3["progress"] == 100.0
    assert jdoc3["result"]["summary"] == "ok"

def test_experiment_repository_fallback_and_export():
    exp_id = experiment_repo.create_experiment(
        video_filename="mongo_test_video.mp4",
        video_duration=5.0,
        strategy="uniform",
        parameters={"target_fps": 5.0},
        original_frames=150,
        selected_frames=25,
        retention_rate=0.1667,
        reduction_rate=0.8333,
        effective_fps=5.0,
        original_size_bytes=500000,
        compressed_size_bytes=100000,
        file_size_reduction_pct=80.0,
        processing_time_sec=0.8,
        info_preservation_score=0.91,
    )
    assert exp_id is not None

    exp = experiment_repo.get_experiment(exp_id)
    assert exp is not None
    assert exp["video_filename"] == "mongo_test_video.mp4"
    assert exp["strategy"] == "uniform"

    json_str = experiment_repo.export_experiment_json(exp_id)
    assert json_str is not None
    assert "mongo_test_video.mp4" in json_str
