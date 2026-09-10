from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class ProcessRequest(BaseModel):
    video_id: str
    strategy: str = Field(default="motion_aware", description="uniform, perceptual, motion_aware")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    generate_video: bool = Field(default=True, description="Whether to encode output MP4")

class CompareRequest(BaseModel):
    video_id: str
    strategies: Optional[List[Dict[str, Any]]] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: str
    error_message: Optional[str] = None

class ExperimentSummary(BaseModel):
    id: str
    experiment_code: str
    created_at: str
    video_filename: str
    strategy: str
    parameters: Dict[str, Any]
    original_frames: int
    selected_frames: int
    retention_rate: float
    reduction_rate: float
    effective_fps: float
    processing_time_sec: float
    file_size_reduction_pct: Optional[float] = None
    info_preservation_score: Optional[float] = None
