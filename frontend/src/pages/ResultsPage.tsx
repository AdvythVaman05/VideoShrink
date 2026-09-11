import React from 'react';
import { Download, RotateCcw, Percent, HardDrive, Layers, Film, ShieldCheck } from 'lucide-react';
import { VideoComparison } from '../components/VideoComparison';
import { FrameTimeline } from '../components/FrameTimeline';
import { DiagnosticsPanel } from '../components/DiagnosticsPanel';
import { api } from '../lib/api';
import { formatBytes, formatPercentage } from '../lib/utils';
import type { ProcessResultsResponse, VideoMetadata } from '../types/api';

interface ResultsPageProps {
  results: ProcessResultsResponse;
  originalMetadata?: VideoMetadata;
  onStartOver: () => void;
}

export const ResultsPage: React.FC<ResultsPageProps> = ({
  results,
  originalMetadata,
  onStartOver,
}) => {
  const { metrics, failure_analysis, benchmark, timeline, job_id, strategy } = results;

  const originalFrames = metrics.original_frames ?? metrics.original_frame_count ?? 0;
  const selectedFrames = metrics.selected_frames ?? metrics.selected_frame_count ?? 0;
  const framesRemoved = metrics.frames_removed ?? Math.max(0, originalFrames - selectedFrames);

  const originalBytes = metrics.original_size_mb
    ? metrics.original_size_mb * 1024 * 1024
    : (metrics.original_file_size_bytes ?? 0);
  const compressedBytes = metrics.compressed_size_mb
    ? metrics.compressed_size_mb * 1024 * 1024
    : (metrics.compressed_file_size_bytes ?? 0);

  const originalFps = results.video_metadata?.fps ?? originalMetadata?.fps ?? metrics.original_fps ?? 30;
  const effectiveFps = metrics.effective_fps ?? 0;
  const processingTimeSec = metrics.processing_time_sec ?? metrics.processing_time_seconds ?? 0;

  const proxyFidelity = benchmark?.proxy_fidelity_score ?? metrics.feature_preservation_index ?? 0;
  const motionPreservation = benchmark?.motion_coverage_score ?? metrics.motion_preservation_score ?? 0;

  const hasOutputVideo = Boolean(
    typeof results.output_video === 'object'
      ? results.output_video?.exists
      : results.output_video
  );
  const downloadUrl = (typeof results.output_video === 'object' && results.output_video?.download_url)
    ? results.output_video.download_url
    : api.getDownloadUrl(job_id);

  const originalStreamUrl = api.getStreamUrl(results.video_id || job_id, true);
  const compressedStreamUrl = api.getStreamUrl(job_id, false);

  const durationSec = results.video_metadata?.duration_seconds
    ?? originalMetadata?.duration
    ?? metrics.original_duration_sec
    ?? (originalFps > 0 ? originalFrames / originalFps : 0);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-10">
      {/* Header & Main CTAs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#DED7CC] pb-6">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-[#D95F32] font-semibold">
            Compression Verified
          </span>
          <h1 className="text-3xl sm:text-4xl font-serif font-normal text-[#252321] mt-0.5">
            Your video is shrunk.
          </h1>
          <p className="text-xs text-[#77716A] mt-1">
            Algorithm: <span className="capitalize font-semibold text-[#252321]">{strategy.replace('_', ' ')}</span> • Processing completed in{' '}
            {processingTimeSec.toFixed(2)}s
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onStartOver}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] hover:bg-[#EFE8DC] text-xs font-medium text-[#252321] transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Process Another</span>
          </button>

          {hasOutputVideo && (
            <a
              href={downloadUrl}
              download
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#D95F32] hover:bg-[#C24F26] text-white text-xs font-medium shadow-sm transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Download MP4</span>
            </a>
          )}
        </div>
      </div>

      {/* The Big 4 Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Frame Reduction */}
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#77716A] mb-2">
            <span className="text-xs font-medium">Frame Reduction</span>
            <Percent className="w-4 h-4 text-[#D95F32]" />
          </div>
          <div>
            <div className="text-3xl font-serif font-semibold text-[#D95F32]">
              {formatPercentage(metrics.frame_reduction_pct ?? 0)}
            </div>
            <div className="text-xs font-mono text-[#77716A] mt-1">
              Pruned {framesRemoved} redundant frames
            </div>
          </div>
        </div>

        {/* Metric 2: Storage Reduction */}
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#77716A] mb-2">
            <span className="text-xs font-medium">Storage Reduction</span>
            <HardDrive className="w-4 h-4 text-[#D95F32]" />
          </div>
          <div>
            <div className="text-3xl font-serif font-semibold text-[#252321]">
              {formatPercentage(metrics.file_size_reduction_pct ?? 0)}
            </div>
            <div className="text-xs font-mono text-[#77716A] mt-1 truncate">
              {formatBytes(originalBytes)} → {formatBytes(compressedBytes)}
            </div>
          </div>
        </div>

        {/* Metric 3: Retained Frames */}
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#77716A] mb-2">
            <span className="text-xs font-medium">Retained Frames</span>
            <Layers className="w-4 h-4 text-[#D95F32]" />
          </div>
          <div>
            <div className="text-3xl font-serif font-semibold text-[#252321]">
              {selectedFrames}
              <span className="text-base font-normal text-[#77716A]"> / {originalFrames}</span>
            </div>
            <div className="text-xs font-mono text-[#77716A] mt-1">
              Keyframes indexed & preserved
            </div>
          </div>
        </div>

        {/* Metric 4: Effective FPS */}
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#77716A] mb-2">
            <span className="text-xs font-medium">Effective Frame Rate</span>
            <Film className="w-4 h-4 text-[#D95F32]" />
          </div>
          <div>
            <div className="text-3xl font-serif font-semibold text-[#252321]">
              {effectiveFps.toFixed(1)}
              <span className="text-base font-normal text-[#77716A]"> / {originalFps.toFixed(1)} fps</span>
            </div>
            <div className="text-xs font-mono text-[#77716A] mt-1">
              Maintains full temporal span
            </div>
          </div>
        </div>
      </div>

      {/* Visual / Motion Preservation Scores */}
      <div className="p-4 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#D95F32]" />
          <span className="text-xs font-semibold text-[#252321]">Preservation Scores (Proxy Metrics):</span>
        </div>

        <div className="flex items-center gap-6 text-xs font-mono">
          <div>
            <span className="text-[#77716A]">Proxy Fidelity: </span>
            <span className="font-semibold text-[#252321]">
              {proxyFidelity.toFixed(3)}
            </span>
          </div>
          <div>
            <span className="text-[#77716A]">Motion Coverage: </span>
            <span className="font-semibold text-[#252321]">
              {motionPreservation.toFixed(3)}
            </span>
          </div>
          <div>
            <span className="text-[#77716A]">Compute Latency: </span>
            <span className="font-semibold text-[#252321]">
              {processingTimeSec.toFixed(2)}s
            </span>
          </div>
        </div>
      </div>

      {/* Video Synchronizer */}
      {hasOutputVideo && (
        <VideoComparison
          jobId={job_id}
          originalStreamUrl={originalStreamUrl}
          compressedStreamUrl={compressedStreamUrl}
          metrics={metrics}
        />
      )}

      {/* Frame Timeline Barcode */}
      {timeline && timeline.length > 0 && (
        <FrameTimeline
          originalFrameCount={originalFrames}
          selectedIndices={timeline}
          durationSeconds={durationSec}
        />
      )}

      {/* Quality Diagnostics & Failure Analysis */}
      <DiagnosticsPanel
        failureAnalysis={failure_analysis}
        benchmark={benchmark}
        currentStrategy={strategy}
      />
    </div>
  );
};
