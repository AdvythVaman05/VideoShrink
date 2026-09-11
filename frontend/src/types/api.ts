export interface VideoMetadata {
  filename: string;
  duration: number;
  frame_count: number;
  fps: number;
  width: number;
  height: number;
  file_size_bytes: number;
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
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  error_message: string | null;
}

export interface CompressionMetrics {
  original_frame_count: number;
  selected_frame_count: number;
  frame_reduction_pct: number;
  original_file_size_bytes: number;
  compressed_file_size_bytes: number;
  file_size_reduction_pct: number;
  original_fps: number;
  effective_fps: number;
  processing_time_seconds: number;
  motion_preservation_score: number;
  feature_preservation_index: number;
}

export interface BenchmarkResult {
  strategy: string;
  frame_reduction_pct: number;
  feature_preservation_index: number;
  motion_preservation_score: number;
  processing_time_seconds: number;
}

export interface FailureAnalysis {
  information_loss_risk: 'low' | 'medium' | 'high';
  temporal_jerkiness_score: number;
  compression_artifacts_detected: boolean;
  warnings: string[];
  recommendations: string[];
}

export interface ProcessResultsResponse {
  job_id: string;
  video_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  strategy: string;
  parameters: Record<string, unknown>;
  metrics: CompressionMetrics;
  benchmark: Record<string, BenchmarkResult>;
  failure_analysis: FailureAnalysis;
  timeline: number[];
  output_video: string | null;
  error_message: string | null;
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
