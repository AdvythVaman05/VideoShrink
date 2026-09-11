import React, { useState } from 'react';
import { StrategyCard } from '../components/StrategyCard';
import { formatBytes, formatDuration } from '../lib/utils';
import type {
  UploadResponse,
  SamplingStrategy,
  StrategyParams,
  ProcessRequest,
} from '../types/api';
import { FileVideo, ArrowLeft, Play } from 'lucide-react';

interface ConfigPageProps {
  uploadData: UploadResponse;
  onStartProcessing: (req: ProcessRequest) => Promise<void>;
  onReset: () => void;
}

export const ConfigPage: React.FC<ConfigPageProps> = ({
  uploadData,
  onStartProcessing,
  onReset,
}) => {
  const [strategy, setStrategy] = useState<SamplingStrategy>('perceptual');
  const [params, setParams] = useState<StrategyParams>({
    stride: 2,
    threshold: 0.15,
    motion_threshold: 2.0,
    min_interval: 1,
    max_interval: 30,
  });
  const [generateVideo, setGenerateVideo] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { metadata } = uploadData;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      let strategyParams: Record<string, unknown> = {};
      if (strategy === 'uniform') {
        strategyParams = { stride: params.stride || 2 };
      } else if (strategy === 'perceptual') {
        strategyParams = { threshold: params.threshold ?? 0.15 };
      } else if (strategy === 'motion_aware') {
        strategyParams = {
          motion_threshold: params.motion_threshold ?? 2.0,
          min_interval: params.min_interval ?? 1,
          max_interval: params.max_interval ?? 30,
        };
      }

      await onStartProcessing({
        video_id: uploadData.video_id,
        strategy,
        parameters: strategyParams,
        generate_video: generateVideo,
      });
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to launch compression job.'
      );
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-8">
      {/* Top Back & Title Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[#77716A] hover:text-[#252321] mb-2 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Upload a different video</span>
          </button>
          <h1 className="text-2xl sm:text-3xl font-serif font-normal text-[#252321]">
            Configure Compression
          </h1>
          <p className="text-xs text-[#77716A] mt-0.5">
            Select sampling heuristic and tuning parameters for dataset reduction
          </p>
        </div>
      </div>

      {/* Video Metadata Inspector Pills */}
      <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
        <div className="flex items-center gap-2 mb-3">
          <FileVideo className="w-4 h-4 text-[#D95F32]" />
          <h3 className="font-semibold text-sm text-[#252321] truncate">
            {uploadData.filename}
          </h3>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-1">
          <div className="bg-[#F7F3EC] p-2.5 rounded-xl border border-[#DED7CC]">
            <div className="text-[11px] font-mono text-[#77716A]">Duration</div>
            <div className="text-sm font-semibold font-mono text-[#252321] mt-0.5">
              {formatDuration(metadata.duration)}
            </div>
          </div>

          <div className="bg-[#F7F3EC] p-2.5 rounded-xl border border-[#DED7CC]">
            <div className="text-[11px] font-mono text-[#77716A]">Total Frames</div>
            <div className="text-sm font-semibold font-mono text-[#252321] mt-0.5">
              {metadata.frame_count}
            </div>
          </div>

          <div className="bg-[#F7F3EC] p-2.5 rounded-xl border border-[#DED7CC]">
            <div className="text-[11px] font-mono text-[#77716A]">Frame Rate</div>
            <div className="text-sm font-semibold font-mono text-[#252321] mt-0.5">
              {metadata.fps.toFixed(1)} fps
            </div>
          </div>

          <div className="bg-[#F7F3EC] p-2.5 rounded-xl border border-[#DED7CC]">
            <div className="text-[11px] font-mono text-[#77716A]">Resolution</div>
            <div className="text-sm font-semibold font-mono text-[#252321] mt-0.5">
              {metadata.width}×{metadata.height}
            </div>
          </div>

          <div className="bg-[#F7F3EC] p-2.5 rounded-xl border border-[#DED7CC] col-span-2 sm:col-span-1">
            <div className="text-[11px] font-mono text-[#77716A]">Raw File Size</div>
            <div className="text-sm font-semibold font-mono text-[#252321] mt-0.5">
              {formatBytes(metadata.file_size_bytes)}
            </div>
          </div>
        </div>
      </div>

      {/* Sampling Strategy Selection */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-semibold text-[#252321] mb-2">
            Sampling Strategy & Algorithm
          </label>
          <StrategyCard
            selectedStrategy={strategy}
            onSelectStrategy={setStrategy}
            params={params}
            onParamsChange={setParams}
          />
        </div>

        {/* Generate Video Option */}
        <div className="p-4 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] shadow-xs flex items-center justify-between">
          <div>
            <span className="font-semibold text-sm text-[#252321]">
              Reconstruct Downsampled MP4 Video
            </span>
            <p className="text-xs text-[#77716A] mt-0.5">
              Uses FFmpeg (or OpenCV fallback) to encode the selected frames into a downloadable MP4.
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={generateVideo}
              onChange={(e) => setGenerateVideo(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-[#EFE8DC] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-[#DED7CC] after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#D95F32]"></div>
          </label>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-[#FDF2F0] border border-[#F5C2B8] text-[#C24F26] text-xs">
            {errorMessage}
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onReset}
            className="px-5 py-2.5 rounded-xl border border-[#DED7CC] text-sm font-medium text-[#77716A] hover:text-[#252321] hover:bg-[#FFFFFF] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#D95F32] hover:bg-[#C24F26] text-white text-sm font-medium shadow-sm transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>{isSubmitting ? 'Initializing Job...' : 'Run VideoShrink Compression'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
