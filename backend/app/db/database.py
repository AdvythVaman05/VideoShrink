import sqlite3
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.app.config import settings

class ExperimentDatabase:
    """
    Lightweight SQLite database for logging and querying experiment runs.
    Ensures complete reproducibility and JSON exportability.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    experiment_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    video_filename TEXT NOT NULL,
                    video_duration REAL,
                    strategy TEXT NOT NULL,
                    parameters TEXT,
                    original_frames INTEGER,
                    selected_frames INTEGER,
                    retention_rate REAL,
                    reduction_rate REAL,
                    effective_fps REAL,
                    original_size_bytes INTEGER,
                    compressed_size_bytes INTEGER,
                    file_size_reduction_pct REAL,
                    processing_time_sec REAL,
                    info_preservation_score REAL,
                    output_video_path TEXT,
                    failure_summary TEXT,
                    quality_summary TEXT
                )
            """)
            # Gracefully handle adding quality_summary if table already existed without it
            try:
                conn.execute("ALTER TABLE experiments ADD COLUMN quality_summary TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()

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
    ) -> str:
        exp_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        exp_code = f"VS-{now.year}-{uuid.uuid4().hex[:4].upper()}"

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO experiments (
                    id, experiment_code, video_filename, video_duration,
                    strategy, parameters, original_frames, selected_frames,
                    retention_rate, reduction_rate, effective_fps,
                    original_size_bytes, compressed_size_bytes, file_size_reduction_pct,
                    processing_time_sec, info_preservation_score, output_video_path,
                    failure_summary, quality_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp_id,
                exp_code,
                video_filename,
                video_duration,
                strategy,
                json.dumps(parameters),
                original_frames,
                selected_frames,
                round(retention_rate, 4),
                round(reduction_rate, 4),
                round(effective_fps, 2),
                original_size_bytes,
                compressed_size_bytes,
                file_size_reduction_pct,
                round(processing_time_sec, 2),
                info_preservation_score,
                output_video_path,
                json.dumps(failure_summary) if failure_summary else None,
                json.dumps(quality_summary) if quality_summary else None,
            ))
            conn.commit()

        # Dual-mode sync: also sync to MongoDB if configured
        try:
            from backend.app.database.mongodb import get_mongo_db
            mongo_db = get_mongo_db()
            if mongo_db is not None:
                doc = {
                    "id": exp_id,
                    "experiment_code": exp_code,
                    "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
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
                mongo_db["experiments"].update_one({"id": exp_id}, {"$set": doc}, upsert=True)
        except Exception:
            pass

        return exp_id

    def get_experiment(self, exp_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM experiments WHERE id = ? OR experiment_code = ?", (exp_id, exp_id))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("parameters"):
                data["parameters"] = json.loads(data["parameters"])
            if data.get("failure_summary"):
                data["failure_summary"] = json.loads(data["failure_summary"])
            if data.get("quality_summary"):
                data["quality_summary"] = json.loads(data["quality_summary"])
            return data

    def export_experiment_json(self, exp_id: str) -> Optional[str]:
        """Export experiment as fully self-contained reproducible JSON."""
        data = self.get_experiment(exp_id)
        if not data:
            return None
        export_payload = {
            "experiment_id": data["id"],
            "experiment_code": data["experiment_code"],
            "timestamp": data["created_at"],
            "video_metadata": {
                "filename": data["video_filename"],
                "duration_seconds": data["video_duration"],
                "original_frames": data["original_frames"],
                "original_size_bytes": data["original_size_bytes"],
            },
            "sampling_configuration": {
                "strategy": data["strategy"],
                "hyperparameters": data["parameters"],
            },
            "results": {
                "selected_frames": data["selected_frames"],
                "retention_rate": data["retention_rate"],
                "reduction_rate": data["reduction_rate"],
                "effective_fps": data["effective_fps"],
                "compressed_size_bytes": data["compressed_size_bytes"],
                "file_size_reduction_pct": data["file_size_reduction_pct"],
                "processing_time_sec": data["processing_time_sec"],
            },
            "evaluation_metrics": {
                "visual_data_preservation_proxy_score": data["info_preservation_score"],
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

    def list_experiments(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                data = dict(row)
                if data.get("parameters"):
                    data["parameters"] = json.loads(data["parameters"])
                if data.get("failure_summary"):
                    data["failure_summary"] = json.loads(data["failure_summary"])
                if data.get("quality_summary"):
                    data["quality_summary"] = json.loads(data["quality_summary"])
                results.append(data)
            return results

db = ExperimentDatabase()
