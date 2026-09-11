import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { formatBytes } from '../lib/utils';
import type { CompressionMetrics } from '../types/api';

interface VideoComparisonProps {
  jobId: string;
  originalStreamUrl: string;
  compressedStreamUrl: string;
  metrics: CompressionMetrics;
}

export const VideoComparison: React.FC<VideoComparisonProps> = ({
  originalStreamUrl,
  compressedStreamUrl,
  metrics,
}) => {
  const originalRef = useRef<HTMLVideoElement>(null);
  const compressedRef = useRef<HTMLVideoElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Sync play / pause
  const togglePlay = () => {
    if (isPlaying) {
      originalRef.current?.pause();
      compressedRef.current?.pause();
      setIsPlaying(false);
    } else {
      originalRef.current?.play().catch(() => {});
      compressedRef.current?.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleRestart = () => {
    if (originalRef.current && compressedRef.current) {
      originalRef.current.currentTime = 0;
      compressedRef.current.currentTime = 0;
      setCurrentTime(0);
      originalRef.current.play().catch(() => {});
      compressedRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (originalRef.current) {
      setCurrentTime(originalRef.current.currentTime);
      if (originalRef.current.duration && !isNaN(originalRef.current.duration)) {
        setDuration(originalRef.current.duration);
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (originalRef.current) originalRef.current.currentTime = time;
    if (compressedRef.current) compressedRef.current.currentTime = time;
  };

  const toggleMute = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    if (originalRef.current) originalRef.current.muted = nextMuted;
    if (compressedRef.current) compressedRef.current.muted = nextMuted;
  };

  useEffect(() => {
    const orig = originalRef.current;
    if (!orig) return;

    const handleLoadedMetadata = () => {
      if (orig.duration && !isNaN(orig.duration)) {
        setDuration(orig.duration);
      }
    };
    orig.addEventListener('loadedmetadata', handleLoadedMetadata);
    return () => {
      orig.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, []);

  return (
    <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="font-semibold text-base text-[#252321]">
            Side-by-Side Video Synchronizer
          </h3>
          <p className="text-xs text-[#77716A]">
            Compare original sequence with the information-preserved compressed output
          </p>
        </div>

        {/* Global Synchronized Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#252321] hover:bg-[#3D3A37] text-white text-xs font-medium transition-colors"
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>Pause Both</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Play Both</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleRestart}
            title="Restart videos"
            className="p-1.5 rounded-lg border border-[#DED7CC] hover:bg-[#EFE8DC] text-[#252321] transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={toggleMute}
            title={isMuted ? 'Unmute' : 'Mute'}
            className="p-1.5 rounded-lg border border-[#DED7CC] hover:bg-[#EFE8DC] text-[#252321] transition-colors"
          >
            {isMuted ? (
              <VolumeX className="w-4 h-4 text-[#77716A]" />
            ) : (
              <Volume2 className="w-4 h-4 text-[#D95F32]" />
            )}
          </button>
        </div>
      </div>

      {/* Videos Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Original */}
        <div className="flex flex-col rounded-xl overflow-hidden border border-[#DED7CC] bg-[#141210]">
          <div className="p-2.5 bg-[#252321] text-white text-xs flex items-center justify-between">
            <span className="font-semibold tracking-wide flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              Original Dataset Video
            </span>
            <span className="font-mono text-[11px] text-[#A29A90]">
              {metrics.original_frame_count} frames • {metrics.original_fps.toFixed(1)} fps •{' '}
              {formatBytes(metrics.original_file_size_bytes)}
            </span>
          </div>
          <div className="relative aspect-video flex items-center justify-center bg-black">
            <video
              ref={originalRef}
              src={originalStreamUrl}
              muted={isMuted}
              playsInline
              onTimeUpdate={handleTimeUpdate}
              onEnded={() => setIsPlaying(false)}
              className="w-full h-full object-contain"
            />
          </div>
        </div>

        {/* Compressed */}
        <div className="flex flex-col rounded-xl overflow-hidden border border-[#D95F32]/50 bg-[#141210]">
          <div className="p-2.5 bg-[#D95F32] text-white text-xs flex items-center justify-between">
            <span className="font-semibold tracking-wide flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
              VideoShrink Compressed
            </span>
            <span className="font-mono text-[11px] text-white/90">
              {metrics.selected_frame_count} frames • {metrics.effective_fps.toFixed(1)} fps •{' '}
              {formatBytes(metrics.compressed_file_size_bytes)}
            </span>
          </div>
          <div className="relative aspect-video flex items-center justify-center bg-black">
            <video
              ref={compressedRef}
              src={compressedStreamUrl}
              muted={isMuted}
              playsInline
              className="w-full h-full object-contain"
            />
          </div>
        </div>
      </div>

      {/* Synchronized timeline scrubber */}
      <div className="mt-4 pt-3 border-t border-[#EFE8DC] flex items-center gap-3">
        <span className="font-mono text-xs text-[#77716A] w-12 text-right">
          {currentTime.toFixed(1)}s
        </span>
        <input
          type="range"
          min="0"
          max={duration || 1}
          step="0.05"
          value={currentTime}
          onChange={handleSeek}
          className="flex-1 accent-[#D95F32] cursor-pointer"
        />
        <span className="font-mono text-xs text-[#77716A] w-12">
          {(duration || 0).toFixed(1)}s
        </span>
      </div>
    </div>
  );
};
