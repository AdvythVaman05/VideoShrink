export interface VideoMetadata {
  filename: string;
  filepath?: string;
  duration?: number;
  duration_seconds?: number;
  frame_count?: number;
  total_frames?: number;
  fps: number;
  width: number;
  height: number;
  file_size_bytes: number;
  codec?: string | null;
  bitrate_kbps?: number | null;
}

export interface UploadResponse {
  video_id: string;
  filename: string;
  metadata: VideoMetadata;
}

export type SamplingStrategy = 'uniform' | 'perceptual' | 'motion_aware';

export interface StrategyParams {
  stride?: number;
  threshold?: number;
  motion_threshold?: number;
  min_interval?: number;
  max_interval?: number;
}

export interface ProcessRequest {
  video_id: string;
  strategy: SamplingStrategy;
  parameters: Record<string, unknown>;
  generate_video?: boolean;
}

export interface ProcessResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  error_message?: string | null;
}

export interface CancelResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface CompressionMetrics {
  original_frames: number;
  selected_frames: number;
  frames_removed: number;
  frame_reduction_pct: number;
  frame_retention_pct: number;
  original_size_mb: number;
  compressed_size_mb: number | null;
  file_size_reduction_pct: number | null;
  original_duration_sec: number;
  effective_fps: number;
  processing_time_sec: number;
  fps_throughput: number;
  // Fallbacks / legacy aliases
  original_frame_count?: number;
  selected_frame_count?: number;
  original_file_size_bytes?: number;
  compressed_file_size_bytes?: number;
  original_fps?: number;
  processing_time_seconds?: number;
  feature_preservation_index?: number;
  motion_preservation_score?: number;
}

export interface VisualPreservationProxyResult {
  metric_name: string;
  proxy_fidelity_score: number;
  motion_coverage_score: number;
  temporal_coverage_score: number;
  sharpness_preservation_ratio: number;
  disclaimer: string;
}

export interface BenchmarkResult {
  strategy?: string;
  frame_reduction_pct?: number;
  feature_preservation_index?: number;
  motion_preservation_score?: number;
  processing_time_seconds?: number;
}

export interface SensitiveSegment {
  start_sec: number;
  end_sec: number;
  start_time_formatted: string;
  end_time_formatted: string;
  reasons: string[];
  severity: 'high' | 'medium' | 'low';
  recommendation: string;
}

export interface FailureAnalysis {
  sensitive_segments_count: number;
  segments: SensitiveSegment[];
  information_loss_risk?: 'low' | 'medium' | 'high';
  temporal_jerkiness_score?: number;
  compression_artifacts_detected?: boolean;
  warnings?: string[];
  recommendations?: string[];
}

export interface TimelinePoint {
  frame_idx: number;
  timestamp: number;
  is_selected: boolean;
  motion_score: number;
  similarity_score: number;
  is_scene_cut: boolean;
  is_blurry: boolean;
}

export interface PreviewFrame {
  frame_idx: number;
  timestamp_sec: number;
  timestamp_formatted: string;
  selection_reason: string;
  thumbnail_base64: string;
  motion_score?: number | null;
  similarity_score?: number | null;
  blur_score?: number | null;
}

export interface OutputVideoInfo {
  exists: boolean;
  filename: string | null;
  file_size_bytes: number | null;
  download_url: string | null;
}

export interface ProcessResultsResponse {
  job_id: string;
  experiment_id?: string;
  video_id?: string;
  video_metadata?: VideoMetadata;
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  strategy: string;
  parameters: Record<string, unknown>;
  metrics: CompressionMetrics;
  benchmark: VisualPreservationProxyResult;
  failure_analysis: FailureAnalysis;
  timeline: (TimelinePoint | number)[];
  preview_frames?: PreviewFrame[];
  output_video: OutputVideoInfo | string | null;
  error_message?: string | null;
}

export interface ExperimentSummary {
  experiment_id: string;
  video_id: string;
  filename: string;
  strategy: string;
  parameters: Record<string, unknown>;
  frame_reduction_pct: number;
  file_size_reduction_pct: number;
  feature_preservation_index: number;
  processing_time_seconds: number;
  timestamp: string;
}

export interface ExperimentListResponse {
  experiments: ExperimentSummary[];
}
