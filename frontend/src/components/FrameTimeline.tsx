import React, { useMemo } from 'react';
import { BarChart3 } from 'lucide-react';

interface FrameTimelineProps {
  originalFrameCount: number;
  selectedIndices: number[];
  durationSeconds: number;
}

export const FrameTimeline: React.FC<FrameTimelineProps> = ({
  originalFrameCount,
  selectedIndices,
  durationSeconds,
}) => {
  // Compute temporal density in 60 bins across the video length
  const densityBins = useMemo(() => {
    const numBins = 60;
    const bins = new Array(numBins).fill(0);
    const binSize = originalFrameCount / numBins;

    if (binSize <= 0) return bins;

    selectedIndices.forEach((idx) => {
      const binIdx = Math.min(numBins - 1, Math.floor(idx / binSize));
      bins[binIdx] += 1;
    });

    const maxCount = Math.max(...bins, 1);
    return bins.map((count) => count / maxCount);
  }, [originalFrameCount, selectedIndices]);

  return (
    <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#D95F32]" />
            <h3 className="font-semibold text-base text-[#252321]">
              Frame Selection Barcode & Temporal Density
            </h3>
          </div>
          <p className="text-xs text-[#77716A] mt-0.5">
            Visual inspection of preserved keyframes along the video timeline
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-[#77716A]">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#D95F32]" />
            <span>Preserved ({selectedIndices.length})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#EFE8DC]" />
            <span>Pruned ({originalFrameCount - selectedIndices.length})</span>
          </div>
        </div>
      </div>

      {/* Barcode Strip */}
      <div className="space-y-1.5">
        <div className="h-10 w-full bg-[#F7F3EC] rounded-lg border border-[#DED7CC] relative overflow-hidden flex items-stretch">
          <svg className="w-full h-full" preserveAspectRatio="none" viewBox={`0 0 ${originalFrameCount} 100`}>
            {selectedIndices.map((idx) => (
              <line
                key={idx}
                x1={idx}
                y1={0}
                x2={idx}
                y2={100}
                stroke="#D95F32"
                strokeWidth={Math.max(1, originalFrameCount / 600)}
                opacity={0.85}
              />
            ))}
          </svg>
        </div>

        {/* Temporal Density Activity Profile */}
        <div className="pt-2">
          <div className="flex items-center justify-between text-[11px] font-mono text-[#77716A] mb-1">
            <span>Dynamic Sampling Rate (Frames/Second Preserved)</span>
            <span>Cluster Density</span>
          </div>
          <div className="h-7 w-full flex items-end gap-0.5 bg-[#FDFBF7] rounded p-1 border border-[#EFE8DC]">
            {densityBins.map((height, i) => (
              <div
                key={i}
                style={{ height: `${Math.max(12, height * 100)}%` }}
                className={`flex-1 rounded-xs transition-all ${
                  height > 0.6
                    ? 'bg-[#D95F32]'
                    : height > 0.2
                    ? 'bg-[#E0835F]'
                    : 'bg-[#EFE8DC]'
                }`}
                title={`Interval ${i + 1}: ${Math.round(height * 100)}% density`}
              />
            ))}
          </div>
        </div>

        {/* Timeline Axis Labels */}
        <div className="flex justify-between text-[11px] font-mono text-[#77716A] pt-1">
          <span>0.0s (Frame #0)</span>
          <span>
            {durationSeconds ? `${(durationSeconds / 2).toFixed(1)}s` : 'Midpoint'}
          </span>
          <span>
            {durationSeconds ? `${durationSeconds.toFixed(1)}s` : ''} (Frame #{originalFrameCount})
          </span>
        </div>
      </div>
    </div>
  );
};
