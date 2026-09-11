import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.video.reader import VideoReader
from backend.app.services.job_runner import job_runner
from backend.app.evaluation.comparison import StrategyComparator
from backend.app.db.database import db
from backend.app.api.schemas import ProcessRequest, CompareRequest, JobStatusResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

# In-memory mapping of video_id -> filepath
uploaded_videos: dict[str, Path] = {}

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Accepts video upload, validates format and size, extracts metadata.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format '{ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    import re
    raw_name = Path(file.filename).name if file.filename else "upload.mp4"
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_name)

    video_id = str(uuid.uuid4())
    save_filename = f"{video_id}_{safe_name}"
    save_path = settings.UPLOAD_DIR / save_filename

    # Save uploaded file
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save video: {str(e)}")
    finally:
        await file.close()

    # Size check
    file_size_mb = save_path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Video file exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB (received {file_size_mb:.1f}MB)."
        )

    # Extract metadata
    try:
        reader = VideoReader(save_path)
        meta = reader.get_metadata()
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse video metadata: {str(e)}. Video may be corrupted."
        )

    if meta.duration_seconds > settings.MAX_VIDEO_DURATION_SEC:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Video duration ({meta.duration_formatted}) exceeds maximum limit of {settings.MAX_VIDEO_DURATION_SEC} seconds."
        )

    uploaded_videos[video_id] = save_path

    return {
        "video_id": video_id,
        "filename": file.filename,
        "metadata": meta.to_dict()
    }

@router.post("/sample/load")
async def load_sample_benchmark():
    """
    Loads the synthetic benchmark sample video directly for immediate exploration.
    """
    sample_path = settings.BASE_DIR / "sample_data" / "benchmark_sample.mp4"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Synthetic benchmark sample video not found on server.")

    video_id = str(uuid.uuid4())
    save_filename = f"{video_id}_benchmark_sample.mp4"
    dest_path = settings.UPLOAD_DIR / save_filename
    shutil.copyfile(sample_path, dest_path)

    reader = VideoReader(dest_path)
    meta = reader.get_metadata()
    uploaded_videos[video_id] = dest_path

    return {
        "video_id": video_id,
        "filename": "benchmark_sample.mp4",
        "metadata": meta.to_dict()
    }

@router.get("/video/{video_id}/metadata")
async def get_metadata(video_id: str):
    """Fetch metadata for an uploaded video."""
    import re
    safe_video_id = re.sub(r"[^a-zA-Z0-9_-]", "", video_id)
    if not safe_video_id:
        raise HTTPException(status_code=400, detail="Invalid video ID format.")

    video_path = uploaded_videos.get(safe_video_id)
    if not video_path or not video_path.exists():
        # Check if it exists directly on disk
        candidates = list(settings.UPLOAD_DIR.glob(f"{safe_video_id}_*"))
        if candidates:
            video_path = candidates[0]
            uploaded_videos[safe_video_id] = video_path
        else:
            raise HTTPException(status_code=404, detail=f"Video ID '{safe_video_id}' not found.")

    try:
        reader = VideoReader(video_path)
        return reader.get_metadata().to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading video: {str(e)}")

@router.post("/process")
async def start_processing(request: ProcessRequest):
    """
    Submits an asynchronous video sampling and reconstruction job.
    """
    import re
    safe_video_id = re.sub(r"[^a-zA-Z0-9_-]", "", request.video_id)
    if not safe_video_id:
        raise HTTPException(status_code=400, detail="Invalid video ID format.")

    video_path = uploaded_videos.get(safe_video_id)
    if not video_path or not video_path.exists():
        candidates = list(settings.UPLOAD_DIR.glob(f"{safe_video_id}_*"))
        if candidates:
            video_path = candidates[0]
            uploaded_videos[safe_video_id] = video_path
        else:
            raise HTTPException(status_code=404, detail=f"Video ID '{safe_video_id}' not found.")

    job_id = job_runner.create_job()
    job_runner.submit_processing_job(
        job_id=job_id,
        video_path=video_path,
        strategy_name=request.strategy,
        strategy_params=request.parameters,
        generate_video=request.generate_video
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Job {job_id} queued for {request.strategy} processing."
    }

@router.get("/process/{job_id}/status")
async def get_job_status(job_id: str):
    """Poll job progress and status."""
    import re
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id)
    job = job_runner.get_job(safe_job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job ID '{safe_job_id}' not found.")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=round(job.progress, 1),
        current_step=job.current_step,
        error_message=job.error_message
    )

@router.get("/process/{job_id}/results")
async def get_job_results(job_id: str):
    """Fetch completed results of a processing job."""
    import re
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id)
    job = job_runner.get_job(safe_job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job ID '{safe_job_id}' not found.")

    if job.status == "processing" or job.status == "pending":
        return {
            "job_id": safe_job_id,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step
        }

    if job.status == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Job processing failed: {job.error_message}"
        )

    return job.result

@router.get("/video/{job_id}/download")
async def download_video(job_id: str):
    """Download the optimized MP4 video produced by a job."""
    import re
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id)
    job = job_runner.get_job(safe_job_id)
    if not job or not job.result:
        # Try checking disk
        candidates = list(settings.PROCESSED_DIR.glob(f"optimized_{safe_job_id}_*.mp4"))
        if candidates:
            return FileResponse(
                path=candidates[0],
                media_type="video/mp4",
                filename=candidates[0].name
            )
        raise HTTPException(status_code=404, detail="Optimized video not found.")

    out_info = job.result.get("output_video", {})
    filename = out_info.get("filename")
    if not filename:
        raise HTTPException(status_code=404, detail="No output video was generated for this job.")

    # Guard filename against path traversal
    safe_out_filename = Path(filename).name
    file_path = settings.PROCESSED_DIR / safe_out_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Optimized video file is missing from storage.")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=safe_out_filename,
        headers={"Content-Disposition": f'attachment; filename="{safe_out_filename}"'}
    )

@router.get("/video/{identifier}/stream")
async def stream_video(identifier: str, original: bool = False):
    """Serve MP4 video for browser playback."""
    import re
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", identifier)
    if not safe_id:
        raise HTTPException(status_code=400, detail="Invalid identifier.")

    if original:
        path = uploaded_videos.get(safe_id)
        if not path or not path.exists():
            candidates = list(settings.UPLOAD_DIR.glob(f"{safe_id}_*"))
            if candidates:
                path = candidates[0]
            else:
                raise HTTPException(status_code=404, detail="Original video not found.")
    else:
        # Optimized video by job_id
        candidates = list(settings.PROCESSED_DIR.glob(f"optimized_{safe_id}_*.mp4"))
        if candidates:
            path = candidates[0]
        else:
            raise HTTPException(status_code=404, detail="Optimized video not found.")

    return FileResponse(path=path, media_type="video/mp4")

@router.post("/compare")
async def compare_video_strategies(request: CompareRequest):
    """
    Run baseline Uniform, Perceptual, and Motion-Aware samplers on the same video
    and return a comparative benchmarking breakdown.
    """
    video_path = uploaded_videos.get(request.video_id)
    if not video_path or not video_path.exists():
        candidates = list(settings.UPLOAD_DIR.glob(f"{request.video_id}_*"))
        if candidates:
            video_path = candidates[0]
            uploaded_videos[request.video_id] = video_path
        else:
            raise HTTPException(status_code=404, detail=f"Video ID '{request.video_id}' not found.")

    try:
        reader = VideoReader(video_path)
        comparison = StrategyComparator.compare_strategies(reader, request.strategies)
        return {
            "video_id": request.video_id,
            "video_metadata": reader.get_metadata().to_dict(),
            "comparison": comparison
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

@router.get("/experiments")
async def list_experiments(limit: int = Query(default=25, ge=1, le=100)):
    """Retrieve experiment run history from SQLite."""
    return db.list_experiments(limit=limit)

@router.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str):
    """Fetch details of a specific experiment."""
    exp = db.get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{exp_id}' not found.")
    return exp

@router.get("/experiments/{exp_id}/export")
async def export_experiment(exp_id: str):
    """Export complete experiment metadata and diagnostics as reproducible JSON."""
    from fastapi.responses import Response
    json_data = db.export_experiment_json(exp_id)
    if not json_data:
        raise HTTPException(status_code=404, detail=f"Experiment '{exp_id}' not found.")
    
    filename = f"experiment_{exp_id[:8]}.json"
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

