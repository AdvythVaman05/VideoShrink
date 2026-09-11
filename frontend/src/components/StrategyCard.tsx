import React from 'react';
import { Sliders, Eye, Activity, Info } from 'lucide-react';
import type { SamplingStrategy, StrategyParams } from '../types/api';

interface StrategyOption {
  id: SamplingStrategy;
  title: string;
  badge?: string;
  tagline: string;
  icon: React.ReactNode;
  description: string;
}

const STRATEGIES: StrategyOption[] = [
  {
    id: 'uniform',
    title: 'Uniform Stride',
    tagline: 'Fixed-interval baseline subsampling',
    icon: <Sliders className="w-5 h-5" />,
    description: 'Samples every N-th frame unconditionally. Fast and predictable, but unaware of scene pauses or rapid motion bursts.',
  },
  {
    id: 'perceptual',
    title: 'Perceptual Similarity',
    badge: 'Recommended for Datasets',
    tagline: 'Histogram cosine distance comparison',
    icon: <Eye className="w-5 h-5" />,
    description: 'Computes HSV color and Sobel gradient differences. Discards visually redundant frames with minimal visual disruption.',
  },
  {
    id: 'motion_aware',
    title: 'Motion-Aware Flow',
    badge: 'Dynamic Action',
    tagline: 'Dense optical flow thresholding',
    icon: <Activity className="w-5 h-5" />,
    description: 'Calculates dense Farneback optical flow. Prunes idle periods while preserving high-acceleration frames with forced keyframe limits.',
  },
];

interface StrategyCardProps {
  selectedStrategy: SamplingStrategy;
  onSelectStrategy: (strategy: SamplingStrategy) => void;
  params: StrategyParams;
  onParamsChange: (newParams: StrategyParams) => void;
}

export const StrategyCard: React.FC<StrategyCardProps> = ({
  selectedStrategy,
  onSelectStrategy,
  params,
  onParamsChange,
}) => {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STRATEGIES.map((strategy) => {
          const isSelected = selectedStrategy === strategy.id;
          return (
            <div
              key={strategy.id}
              onClick={() => onSelectStrategy(strategy.id)}
              className={`relative rounded-xl p-5 border cursor-pointer transition-all flex flex-col justify-between ${
                isSelected
                  ? 'border-[#D95F32] bg-[#FFFFFF] shadow-sm ring-1 ring-[#D95F32]/20'
                  : 'border-[#DED7CC] bg-[#FFFFFF]/70 hover:bg-[#FFFFFF] hover:border-[#D95F32]/50'
              }`}
            >
              {strategy.badge && (
                <span className="absolute -top-2.5 right-4 bg-[#D95F32] text-white text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded-full font-medium shadow-xs">
                  {strategy.badge}
                </span>
              )}

              <div>
                <div className="flex items-center gap-2.5 mb-2">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                      isSelected
                        ? 'bg-[#D95F32] text-white'
                        : 'bg-[#EFE8DC] text-[#77716A]'
                    }`}
                  >
                    {strategy.icon}
                  </div>
                  <div>
                    <h4 className="font-semibold text-sm text-[#252321]">
                      {strategy.title}
                    </h4>
                  </div>
                </div>

                <p className="text-xs text-[#D95F32] font-mono mb-2">
                  {strategy.tagline}
                </p>

                <p className="text-xs text-[#77716A] leading-relaxed">
                  {strategy.description}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-[#EFE8DC] flex items-center justify-between">
                <span className="text-[11px] font-mono text-[#77716A]">
                  {isSelected ? 'Active Selection' : 'Click to select'}
                </span>
                <div
                  className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                    isSelected
                      ? 'border-[#D95F32] bg-[#D95F32]'
                      : 'border-[#DED7CC] bg-white'
                  }`}
                >
                  {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Strategy-Specific Parameters Controls */}
      <div className="p-5 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] shadow-xs">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-4 h-4 text-[#D95F32]" />
          <h4 className="font-semibold text-sm text-[#252321]">
            Tuning Parameters for {STRATEGIES.find((s) => s.id === selectedStrategy)?.title}
          </h4>
        </div>

        {selectedStrategy === 'uniform' && (
          <div className="space-y-4 max-w-lg">
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#252321]">Stride (Sampling Frequency)</span>
                <span className="font-mono text-[#D95F32]">
                  Every {params.stride || 2} frames (~{Math.round(100 / (params.stride || 2))}% retained)
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="20"
                step="1"
                value={params.stride || 2}
                onChange={(e) =>
                  onParamsChange({ ...params, stride: parseInt(e.target.value, 10) })
                }
                className="w-full accent-[#D95F32] cursor-pointer"
              />
              <p className="text-[11px] text-[#77716A] mt-1">
                Stride of 2 keeps 50% of frames; stride of 5 keeps 20% of frames.
              </p>
            </div>
          </div>
        )}

        {selectedStrategy === 'perceptual' && (
          <div className="space-y-4 max-w-lg">
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#252321]">Difference Threshold</span>
                <span className="font-mono text-[#D95F32]">
                  {(params.threshold ?? 0.15).toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0.02"
                max="0.45"
                step="0.01"
                value={params.threshold ?? 0.15}
                onChange={(e) =>
                  onParamsChange({ ...params, threshold: parseFloat(e.target.value) })
                }
                className="w-full accent-[#D95F32] cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-[#77716A] mt-1 font-mono">
                <span>0.05 (High Fidelity / Keep More)</span>
                <span>0.30+ (Aggressive Pruning)</span>
              </div>
            </div>
          </div>
        )}

        {selectedStrategy === 'motion_aware' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#252321]">Motion Magnitude</span>
                <span className="font-mono text-[#D95F32]">
                  {(params.motion_threshold ?? 2.0).toFixed(1)}
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="8.0"
                step="0.1"
                value={params.motion_threshold ?? 2.0}
                onChange={(e) =>
                  onParamsChange({
                    ...params,
                    motion_threshold: parseFloat(e.target.value),
                  })
                }
                className="w-full accent-[#D95F32] cursor-pointer"
              />
              <p className="text-[11px] text-[#77716A] mt-1">
                Optical flow velocity cut-off.
              </p>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#252321]">Min Interval (Frames)</span>
                <span className="font-mono text-[#D95F32]">{params.min_interval ?? 1}</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={params.min_interval ?? 1}
                onChange={(e) =>
                  onParamsChange({
                    ...params,
                    min_interval: parseInt(e.target.value, 10),
                  })
                }
                className="w-full accent-[#D95F32] cursor-pointer"
              />
              <p className="text-[11px] text-[#77716A] mt-1">
                Minimum frame spacing.
              </p>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="text-[#252321]">Max Interval (Forced)</span>
                <span className="font-mono text-[#D95F32]">{params.max_interval ?? 30}</span>
              </div>
              <input
                type="range"
                min="5"
                max="60"
                step="1"
                value={params.max_interval ?? 30}
                onChange={(e) =>
                  onParamsChange({
                    ...params,
                    max_interval: parseInt(e.target.value, 10),
                  })
                }
                className="w-full accent-[#D95F32] cursor-pointer"
              />
              <p className="text-[11px] text-[#77716A] mt-1">
                Forces keyframe if no motion detected.
              </p>
            </div>
          </div>
        )}

        <div className="mt-4 pt-3 border-t border-[#EFE8DC] flex items-center gap-1.5 text-xs text-[#77716A]">
          <Info className="w-3.5 h-3.5 text-[#D95F32] shrink-0" />
          <span>
            Parameters are recorded with full provenance in the experiment tracking SQLite database.
          </span>
        </div>
      </div>
    </div>
  );
};
