import uuid
import json
import logging
import datetime
from typing import Dict, Any, List, Optional
from pymongo.collection import Collection

from backend.app.database.mongodb import get_mongo_db

logger = logging.getLogger("videoshrink.repositories")

def _clean_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strips MongoDB internal _id and normalizes datetime objects to ISO strings."""
    if not doc:
        return None
    d = dict(doc)
    d.pop("_id", None)
    for k, v in list(d.items()):
        if isinstance(v, datetime.datetime):
            d[k] = v.isoformat()
    return d

class VideoRepository:
    """Manages metadata for uploaded and processed source videos in MongoDB 'videos' collection."""
    def __init__(self):
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _get_collection(self) -> Optional[Collection]:
        db = get_mongo_db()
        return db["videos"] if db is not None else None

    def create_video(
        self,
        video_data: Optional[Dict[str, Any]] = None,
        *,
        video_id: Optional[str] = None,
        filename: Optional[str] = None,
        filepath: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if video_data is not None and isinstance(video_data, dict):
            doc = dict(video_data)
        else:
            doc = {}
        if video_id:
            doc["video_id"] = video_id
        if filename:
            doc["filename"] = filename
        if filepath:
            doc["filepath"] = filepath
        if file_size_bytes is not None:
            doc["file_size_bytes"] = file_size_bytes
        if metadata is not None:
            doc["metadata"] = metadata
        doc.update(kwargs)

        now = datetime.datetime.now(datetime.timezone.utc)
        if "created_at" not in doc:
            doc["created_at"] = now
        doc["updated_at"] = now

        vid = doc.get("video_id")
        if not vid:
            vid = str(uuid.uuid4())
            doc["video_id"] = vid

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"video_id": vid}, {"$set": doc}, upsert=True)
            except Exception as e:
                logger.error(f"Error saving video {vid} to MongoDB: {e}")

        # Always keep in memory for immediate hot access
        self._memory_cache[vid] = doc
        return _clean_doc(doc) or doc

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        coll = self._get_collection()
        if coll is not None:
            try:
                doc = coll.find_one({"video_id": video_id})
                if doc:
                    return _clean_doc(doc)
            except Exception as e:
                logger.error(f"Error reading video {video_id} from MongoDB: {e}")

        # Fall back to in-memory cache
        return _clean_doc(self._memory_cache.get(video_id))

    def list_videos(self, limit: int = 50) -> List[Dict[str, Any]]:
        coll = self._get_collection()
        if coll is not None:
            try:
                cursor = coll.find({}, {"_id": False}).sort("created_at", -1).limit(limit)
                return [_clean_doc(d) or d for d in cursor]
            except Exception as e:
                logger.error(f"Error listing videos from MongoDB: {e}")

        # In-memory fallback
        return [_clean_doc(v) or v for v in list(self._memory_cache.values())[:limit]]

class JobRepository:
    """Manages processing job state in MongoDB 'jobs' collection."""
    def __init__(self):
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _get_collection(self) -> Optional[Collection]:
        db = get_mongo_db()
        return db["jobs"] if db is not None else None

    def create_job(
        self,
        job_id: str,
        video_id: str = "",
        strategy: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        strat = strategy or strategy_name or "unknown"
        params = parameters if parameters is not None else (strategy_params or {})
        now = datetime.datetime.now(datetime.timezone.utc)
        doc = {
            "job_id": job_id,
            "video_id": video_id,
            "status": "pending",
            "strategy": strat,
            "parameters": params,
            "progress": 0.0,
            "current_step": "Job queued",
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "result": None,
        }
        doc.update(kwargs)

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"job_id": job_id}, {"$set": doc}, upsert=True)
            except Exception as e:
                logger.error(f"Error creating job {job_id} in MongoDB: {e}")

        self._memory_cache[job_id] = doc
        return _clean_doc(doc) or doc

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        coll = self._get_collection()
        if coll is not None:
            try:
                doc = coll.find_one({"job_id": job_id})
                if doc:
                    return _clean_doc(doc)
            except Exception as e:
                logger.error(f"Error retrieving job {job_id} from MongoDB: {e}")

        return _clean_doc(self._memory_cache.get(job_id))

    def update_progress(self, job_id: str, progress: float, current_step: str) -> bool:
        update_fields = {
            "progress": round(progress, 1),
            "current_step": current_step,
            "status": "processing",
        }
        if job_id in self._memory_cache:
            self._memory_cache[job_id].update(update_fields)

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one(
                    {"job_id": job_id},
                    {
                        "$set": update_fields,
                        "$setOnInsert": {"created_at": datetime.datetime.now(datetime.timezone.utc)}
                    },
                    upsert=True
                )
                return True
            except Exception as e:
                logger.error(f"Error updating progress for job {job_id} in MongoDB: {e}")
                return False
        return True

    def complete_job(
        self,
        job_id: str,
        result: Dict[str, Any],
        processing_time_sec: Optional[float] = None,
        output_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_fields = {
            "status": "completed",
            "progress": 100.0,
            "current_step": "Completed successfully",
            "completed_at": now,
            "result": result,
        }
        if processing_time_sec is not None:
            update_fields["processing_time_seconds"] = processing_time_sec
        if output_info is not None:
            update_fields["output_video"] = output_info

        if job_id in self._memory_cache:
            self._memory_cache[job_id].update(update_fields)

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"job_id": job_id}, {"$set": update_fields}, upsert=True)
                return True
            except Exception as e:
                logger.error(f"Error marking job {job_id} completed in MongoDB: {e}")
                return False
        return True

    def fail_job(self, job_id: str, error_message: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_fields = {
            "status": "failed",
            "current_step": f"Failed: {error_message}",
            "error_message": error_message,
            "completed_at": now,
        }
        if job_id in self._memory_cache:
            self._memory_cache[job_id].update(update_fields)

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"job_id": job_id}, {"$set": update_fields}, upsert=True)
                return True
            except Exception as e:
                logger.error(f"Error marking job {job_id} failed in MongoDB: {e}")
                return False
        return True

    def cancel_job(self, job_id: str, reason: str = "Cancelled by user") -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_fields = {
            "status": "cancelled",
            "current_step": f"Cancelled: {reason}",
            "error_message": reason,
            "completed_at": now,
            "cancelled_at": now,
        }
        if job_id in self._memory_cache:
            self._memory_cache[job_id].update(update_fields)

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.update_one({"job_id": job_id}, {"$set": update_fields}, upsert=True)
                return True
            except Exception as e:
                logger.error(f"Error marking job {job_id} cancelled in MongoDB: {e}")
                return False
        return True

class ExperimentRepository:
    """Manages experiment history and export records in MongoDB 'experiments' collection."""
    def _get_collection(self) -> Optional[Collection]:
        db = get_mongo_db()
        return db["experiments"] if db is not None else None

    def create_experiment(
        self,
        video_filename: str,
        video_duration: float,
        strategy: str,
        parameters: Dict[str, Any],
        original_frames: int,
        selected_frames: int,
        retention_rate: float,
        reduction_rate: float,
        effective_fps: float,
        original_size_bytes: int,
        compressed_size_bytes: Optional[int],
        file_size_reduction_pct: Optional[float],
        processing_time_sec: float,
        info_preservation_score: Optional[float] = None,
        output_video_path: Optional[str] = None,
        failure_summary: Optional[Dict[str, Any]] = None,
        quality_summary: Optional[Dict[str, Any]] = None,
        video_id: Optional[str] = None,
    ) -> str:
        exp_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        exp_code = f"VS-{now.year}-{uuid.uuid4().hex[:4].upper()}"

        doc = {
            "id": exp_id,
            "experiment_code": exp_code,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "video_id": video_id,
            "video_filename": video_filename,
            "video_duration": video_duration,
            "strategy": strategy,
            "parameters": parameters,
            "original_frames": original_frames,
            "selected_frames": selected_frames,
            "retention_rate": round(retention_rate, 4),
            "reduction_rate": round(reduction_rate, 4),
            "effective_fps": round(effective_fps, 2),
            "original_size_bytes": original_size_bytes,
            "compressed_size_bytes": compressed_size_bytes,
            "file_size_reduction_pct": file_size_reduction_pct,
            "processing_time_sec": round(processing_time_sec, 2),
            "info_preservation_score": info_preservation_score,
            "output_video_path": output_video_path,
            "failure_summary": failure_summary,
            "quality_summary": quality_summary,
        }

        coll = self._get_collection()
        if coll is not None:
            try:
                coll.insert_one(doc)
                return exp_id
            except Exception as e:
                logger.error(f"Error inserting experiment into MongoDB: {e}")

        # Fall back to SQLite if MongoDB is not available
        from backend.app.db.database import ExperimentDatabase
        sqlite_db = ExperimentDatabase()
        return sqlite_db.create_experiment(
            video_filename=video_filename,
            video_duration=video_duration,
            strategy=strategy,
            parameters=parameters,
            original_frames=original_frames,
            selected_frames=selected_frames,
            retention_rate=retention_rate,
            reduction_rate=reduction_rate,
            effective_fps=effective_fps,
            original_size_bytes=original_size_bytes,
            compressed_size_bytes=compressed_size_bytes,
            file_size_reduction_pct=file_size_reduction_pct,
            processing_time_sec=processing_time_sec,
            info_preservation_score=info_preservation_score,
            output_video_path=output_video_path,
            failure_summary=failure_summary,
            quality_summary=quality_summary,
        )

    def get_experiment(self, exp_id: str) -> Optional[Dict[str, Any]]:
        coll = self._get_collection()
        if coll is not None:
            try:
                doc = coll.find_one({"$or": [{"id": exp_id}, {"experiment_code": exp_id}]})
                if doc:
                    return _clean_doc(doc)
            except Exception as e:
                logger.error(f"Error fetching experiment {exp_id} from MongoDB: {e}")

        # Fall back to SQLite
        from backend.app.db.database import ExperimentDatabase
        sqlite_db = ExperimentDatabase()
        return sqlite_db.get_experiment(exp_id)

    def list_experiments(self, limit: int = 50) -> List[Dict[str, Any]]:
        coll = self._get_collection()
        if coll is not None:
            try:
                cursor = coll.find({}, {"_id": False}).sort("created_at", -1).limit(limit)
                docs = list(cursor)
                if docs:
                    return [_clean_doc(d) or d for d in docs]
            except Exception as e:
                logger.error(f"Error listing experiments from MongoDB: {e}")

        # Fall back to SQLite
        from backend.app.db.database import ExperimentDatabase
        sqlite_db = ExperimentDatabase()
        return sqlite_db.list_experiments(limit=limit)

    def export_experiment_json(self, exp_id: str) -> Optional[str]:
        data = self.get_experiment(exp_id)
        if not data:
            return None

        export_payload = {
            "experiment_id": data.get("id"),
            "experiment_code": data.get("experiment_code"),
            "timestamp": data.get("created_at"),
            "video_metadata": {
                "filename": data.get("video_filename"),
                "duration_seconds": data.get("video_duration"),
                "original_frames": data.get("original_frames"),
                "original_size_bytes": data.get("original_size_bytes"),
            },
            "sampling_configuration": {
                "strategy": data.get("strategy"),
                "hyperparameters": data.get("parameters"),
            },
            "results": {
                "selected_frames": data.get("selected_frames"),
                "retention_rate": data.get("retention_rate"),
                "reduction_rate": data.get("reduction_rate"),
                "effective_fps": data.get("effective_fps"),
                "compressed_size_bytes": data.get("compressed_size_bytes"),
                "file_size_reduction_pct": data.get("file_size_reduction_pct"),
                "processing_time_sec": data.get("processing_time_sec"),
            },
            "evaluation_metrics": {
                "visual_data_preservation_proxy_score": data.get("info_preservation_score"),
                "metric_type": "Analytical Visual Proxy (Heuristic)",
                "disclaimer": (
                    "PROXY METRIC ONLY: This score quantifies visual motion and temporal coverage heuristics. "
                    "It is NOT equivalent to downstream ML model performance."
                )
            },
            "quality_metrics": data.get("quality_summary") or {},
            "failure_sensitive_segments": data.get("failure_summary") or {},
            "output_video_path": data.get("output_video_path"),
        }
        return json.dumps(export_payload, indent=2)

video_repo = VideoRepository()
job_repo = JobRepository()
experiment_repo = ExperimentRepository()

