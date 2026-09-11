import uuid
import time
import base64
import cv2
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

from backend.app.config import settings
from backend.app.video.reader import VideoReader
from backend.app.video.writer import VideoWriter
from backend.app.sampling.base import SelectionResult
from backend.app.sampling.selector import FrameSelector
from backend.app.analysis.failure import FailureAnalyzer
from backend.app.evaluation.metrics import ReductionMetrics
from backend.app.evaluation.benchmark import VisualPreservationProxyEvaluator
from backend.app.db.database import db
from backend.app.database.repositories import job_repo, experiment_repo

@dataclass
class JobState:
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: float  # 0.0 to 100.0
    current_step: str
    created_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class JobRunner:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, JobState] = {}
        self.writer = VideoWriter()
        self.failure_analyzer = FailureAnalyzer()
        self.benchmark = VisualPreservationProxyEvaluator()

    def create_job(
        self,
        video_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = JobState(
            job_id=job_id,
            status="pending",
            progress=0.0,
            current_step="Job queued"
        )
        try:
            job_repo.create_job(
                job_id=job_id,
                video_id=video_id or "",
                strategy_name=strategy_name or "",
                strategy_params=strategy_params or {},
            )
        except Exception as e:
            import logging
            logging.getLogger("videoshrink").warning(f"Error recording job {job_id} in repo: {e}")
        return job_id

    def get_job(self, job_id: str) -> Optional[JobState]:
        job = self.jobs.get(job_id)
        if job is not None:
            return job

        # Job recovery: check repository (MongoDB / memory) in case worker restarted
        try:
            doc = job_repo.get_job(job_id)
            if doc:
                recovered_job = JobState(
                    job_id=doc.get("job_id", job_id),
                    status=doc.get("status", "pending"),
                    progress=float(doc.get("progress", 0.0)),
                    current_step=doc.get("current_step", ""),
                    error_message=doc.get("error_message"),
                    result=doc.get("result"),
                )
                self.jobs[job_id] = recovered_job
                return recovered_job
        except Exception:
            pass

        return None

    def submit_processing_job(
        self,
        job_id: str,
        video_path: Path,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        generate_video: bool = True,
    ) -> None:
        self.executor.submit(
            self._process_video_task,
            job_id=job_id,
            video_path=video_path,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            generate_video=generate_video
        )

    def _process_video_task(
        self,
        job_id: str,
        video_path: Path,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        generate_video: bool = True
    ) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return

        try:
            job.status = "processing"
            job.progress = 5.0
            job.current_step = "Extracting video metadata..."
            job_repo.update_progress(job_id, 5.0, job.current_step)

            reader = VideoReader(video_path)
            meta = reader.get_metadata()

            job.progress = 10.0
            job.current_step = f"Executing {strategy_name} frame sampling..."
            job_repo.update_progress(job_id, 10.0, job.current_step)

            last_persisted_pct = 10.0
            def update_progress(pct: float, msg: str):
                nonlocal last_persisted_pct
                # Map sampling progress to 10% - 65%
                current_pct = 10.0 + (pct * 0.55)
                job.progress = current_pct
                job.current_step = msg
                if current_pct - last_persisted_pct >= 5.0 or current_pct >= 64.0:
                    last_persisted_pct = current_pct
                    job_repo.update_progress(job_id, current_pct, msg)

            # Run sampling algorithm
            selection = FrameSelector.run_selection(
                strategy_name=strategy_name,
                reader=reader,
                params=strategy_params,
                progress_callback=update_progress
            )

            job.progress = 65.0
            job.current_step = "Analyzing failure risks & sensitive segments..."
            job_repo.update_progress(job_id, 65.0, job.current_step)

            # Failure analysis
            timeline_summary = [
                {
                    "timestamp": r.timestamp_sec,
                    "motion_score": r.motion_score or 0.0,
                    "is_scene_cut": r.is_scene_cut,
                    "is_blurry": r.is_blurry,
                    "is_underexposed": r.is_underexposed,
                    "is_overexposed": r.is_overexposed
                }
                for r in selection.frame_records
            ]
            sensitive_segments = self.failure_analyzer.analyze_timeline(timeline_summary)

            job.progress = 75.0
            job.current_step = "Computing benchmark information fidelity..."
            job_repo.update_progress(job_id, 75.0, job.current_step)
            bench_result = self.benchmark.evaluate(reader, selection)

            # Generate output video if requested
            output_video_path_str = None
            compressed_size_bytes = None
            file_reduction_pct = None

            if generate_video and selection.selected_indices:
                job.progress = 80.0
                job.current_step = "Synthesizing optimized video stream..."
                job_repo.update_progress(job_id, 80.0, job.current_step)
                out_filename = f"optimized_{job_id}_{video_path.stem}.mp4"
                dest_path = settings.PROCESSED_DIR / out_filename

                written_path = self.writer.write_selected_frames(
                    source_video_path=video_path,
                    selected_indices=selection.selected_indices,
                    output_video_path=dest_path,
                    preserve_duration=True
                )
                if written_path.exists():
                    output_video_path_str = str(written_path)
                    compressed_size_bytes = written_path.stat().st_size
                    if meta.file_size_bytes > 0:
                        saved = meta.file_size_bytes - compressed_size_bytes
                        file_reduction_pct = round((saved / meta.file_size_bytes) * 100.0, 2)

            job.progress = 90.0
            job.current_step = "Generating frame previews & timeline data..."
            job_repo.update_progress(job_id, 90.0, job.current_step)

            # Sample key preview frames (up to 12 representative selected frames)
            preview_frames = self._extract_frame_previews(reader, selection)

            # Metrics
            reduction_metrics = ReductionMetrics(
                original_frames=meta.total_frames,
                selected_frames=selection.selected_count,
                original_size_bytes=meta.file_size_bytes,
                compressed_size_bytes=compressed_size_bytes,
                original_duration_sec=meta.duration_seconds,
                processing_time_sec=selection.processing_time_sec
            )

            # Clean filename without uuid prefix
            clean_filename = meta.filename.split("_", 1)[-1] if "_" in meta.filename else meta.filename

            # Calculate quality summary metrics across selected frames
            import numpy as np
            kept_records = [r for r in selection.frame_records if r.is_selected]
            if kept_records:
                mean_blur = float(np.mean([r.blur_score for r in kept_records if r.blur_score is not None] or [0.0]))
                mean_bright = float(np.mean([r.brightness for r in kept_records if r.brightness is not None] or [0.0]))
                mean_contrast = float(np.mean([r.contrast for r in kept_records if r.contrast is not None] or [0.0]))
                blurry_count = sum(1 for r in kept_records if r.is_blurry)
            else:
                mean_blur, mean_bright, mean_contrast, blurry_count = 0.0, 0.0, 0.0, 0

            quality_summary = {
                "mean_blur_score": round(mean_blur, 2),
                "mean_brightness": round(mean_bright, 2),
                "mean_contrast": round(mean_contrast, 2),
                "blurry_frames_count": blurry_count
            }

            # Log to MongoDB / SQLite repository
            exp_id = experiment_repo.create_experiment(
                video_filename=clean_filename,
                video_duration=meta.duration_seconds,
                strategy=strategy_name,
                parameters=strategy_params,
                original_frames=meta.total_frames,
                selected_frames=selection.selected_count,
                retention_rate=selection.retention_rate,
                reduction_rate=selection.reduction_rate,
                effective_fps=selection.effective_fps,
                original_size_bytes=meta.file_size_bytes,
                compressed_size_bytes=compressed_size_bytes,
                file_size_reduction_pct=file_reduction_pct,
                processing_time_sec=selection.processing_time_sec,
                info_preservation_score=bench_result.proxy_fidelity_score,
                output_video_path=output_video_path_str,
                failure_summary={
                    "sensitive_segments_count": len(sensitive_segments),
                    "segments": [s.__dict__ for s in sensitive_segments]
                },
                quality_summary=quality_summary,
                video_id=video_path.stem.split("_")[0] if "_" in video_path.stem else None,
            )

            # Subsample timeline records for UI rendering if very long (max 1000 points)
            timeline_records = self._format_timeline_records(selection.frame_records)

            job.progress = 100.0
            job.status = "completed"
            job.current_step = "Completed successfully"
            job.result = {
                "job_id": job_id,
                "experiment_id": exp_id,
                "video_metadata": meta.to_dict(),
                "strategy": strategy_name,
                "parameters": strategy_params,
                "metrics": reduction_metrics.to_dict(),
                "benchmark": bench_result.to_dict(),
                "failure_analysis": {
                    "sensitive_segments_count": len(sensitive_segments),
                    "segments": [s.__dict__ for s in sensitive_segments]
                },
                "timeline": timeline_records,
                "preview_frames": preview_frames,
                "output_video": {
                    "exists": output_video_path_str is not None,
                    "filename": Path(output_video_path_str).name if output_video_path_str else None,
                    "file_size_bytes": compressed_size_bytes,
                    "download_url": f"/api/video/{job_id}/download" if output_video_path_str else None
                }
            }

            job_repo.complete_job(
                job_id=job_id,
                result=job.result,
                processing_time_sec=selection.processing_time_sec,
                output_info=job.result.get("output_video")
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            job.status = "failed"
            job.error_message = str(e)
            job.current_step = f"Failed: {str(e)}"
            job_repo.fail_job(job_id, error_message=str(e))

    def _extract_frame_previews(
        self,
        reader: VideoReader,
        selection: SelectionResult,
        max_previews: int = 12
    ) -> List[Dict[str, Any]]:
        kept = [r for r in selection.frame_records if r.is_selected]
        if not kept:
            return []

        stride = max(1, len(kept) // max_previews)
        sampled_records = kept[::stride][:max_previews]

        previews = []
        for r in sampled_records:
            rgb_frame = reader.extract_frame_at(r.frame_idx)
            thumb_b64 = None
            if rgb_frame is not None:
                # Resize for thumbnail
                h, w = rgb_frame.shape[:2]
                thumb_w = 240
                thumb_h = int(h * (thumb_w / w))
                thumb = cv2.resize(rgb_frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
                # BGR for imencode
                bgr_thumb = cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR)
                success, buffer = cv2.imencode(".jpg", bgr_thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if success:
                    thumb_b64 = base64.b64encode(buffer).decode("utf-8")

            previews.append({
                "frame_idx": r.frame_idx,
                "timestamp_sec": round(r.timestamp_sec, 2),
                "timestamp_formatted": f"{int(r.timestamp_sec//60):02d}:{r.timestamp_sec%60:05.2f}",
                "selection_reason": r.selection_reason,
                "motion_score": r.motion_score,
                "similarity_score": r.similarity_score,
                "blur_score": r.blur_score,
                "thumbnail_base64": thumb_b64
            })
        return previews

    def _format_timeline_records(
        self,
        records: List[Any],
        max_points: int = 600
    ) -> List[Dict[str, Any]]:
        if not records:
            return []
        step = max(1, len(records) // max_points)
        sampled = records[::step]
        # Always ensure first and last are present
        if records[-1] not in sampled:
            sampled.append(records[-1])

        return [
            {
                "frame_idx": r.frame_idx,
                "timestamp": round(r.timestamp_sec, 2),
                "is_selected": r.is_selected,
                "motion_score": r.motion_score if r.motion_score is not None else 0.0,
                "similarity_score": r.similarity_score if r.similarity_score is not None else 1.0,
                "is_scene_cut": r.is_scene_cut,
                "is_blurry": r.is_blurry,
            }
            for r in sampled
        ]

job_runner = JobRunner()
