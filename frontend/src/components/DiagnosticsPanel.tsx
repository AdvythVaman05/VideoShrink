import React from 'react';
import { ShieldCheck, AlertTriangle, AlertCircle, Award, CheckCircle2 } from 'lucide-react';
import type { FailureAnalysis, BenchmarkResult } from '../types/api';

interface DiagnosticsPanelProps {
  failureAnalysis: FailureAnalysis;
  benchmark: Record<string, BenchmarkResult>;
  currentStrategy: string;
}

export const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({
  failureAnalysis,
  benchmark,
  currentStrategy,
}) => {
  const getRiskBadge = (risk: 'low' | 'medium' | 'high') => {
    switch (risk) {
      case 'low':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#EBF5EE] text-[#1E7E34] border border-[#C3E6CB]">
            <ShieldCheck className="w-3.5 h-3.5" /> Low Risk
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#FFF8E6] text-[#B7791F] border border-[#FEEBAA]">
            <AlertTriangle className="w-3.5 h-3.5" /> Moderate Risk
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#FDF2F0] text-[#C24F26] border border-[#F5C2B8]">
            <AlertCircle className="w-3.5 h-3.5" /> High Information Loss
          </span>
        );
    }
  };

  const benchmarkEntries = Object.entries(benchmark || {});

  return (
    <div className="space-y-6">
      {/* Risk and Jerkiness Card */}
      <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-base text-[#252321]">
              Quality Diagnostics & Failure Analysis
            </h3>
            <p className="text-xs text-[#77716A]">
              Automated heuristics evaluating temporal continuity and artifact likelihood
            </p>
          </div>
          <div>{getRiskBadge(failureAnalysis.information_loss_risk)}</div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div className="p-3.5 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
            <div className="text-xs text-[#77716A] font-medium mb-1">
              Temporal Jerkiness Score
            </div>
            <div className="text-2xl font-mono font-semibold text-[#252321]">
              {(failureAnalysis.temporal_jerkiness_score ?? 0).toFixed(3)}
            </div>
            <p className="text-[11px] text-[#77716A] mt-1">
              Variance of inter-frame intervals. Lower indicates smoother temporal cadence.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
            <div className="text-xs text-[#77716A] font-medium mb-1">
              Artifact Anomaly Flag
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-mono font-semibold text-[#252321]">
                {failureAnalysis.compression_artifacts_detected ? 'Detected' : 'None'}
              </span>
              {!failureAnalysis.compression_artifacts_detected && (
                <CheckCircle2 className="w-5 h-5 text-[#1E7E34]" />
              )}
            </div>
            <p className="text-[11px] text-[#77716A] mt-1">
              Heuristic verification of spatial compression and pixel stability.
            </p>
          </div>
        </div>

        {/* Warnings & Recommendations */}
        {(failureAnalysis.warnings?.length > 0 || failureAnalysis.recommendations?.length > 0) && (
          <div className="mt-4 pt-4 border-t border-[#EFE8DC] space-y-2">
            {failureAnalysis.warnings?.map((warning, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs text-[#C24F26] bg-[#FDF2F0] p-2.5 rounded-lg border border-[#F5C2B8]"
              >
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{warning}</span>
              </div>
            ))}
            {failureAnalysis.recommendations?.map((rec, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs text-[#252321] bg-[#F7F3EC] p-2.5 rounded-lg border border-[#DED7CC]"
              >
                <Award className="w-4 h-4 shrink-0 text-[#D95F32] mt-0.5" />
                <span>{rec}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Multi-Strategy Benchmark Comparison Table */}
      {benchmarkEntries.length > 0 && (
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
          <h3 className="font-semibold text-base text-[#252321] mb-1">
            Sampling Strategy Benchmark Matrix
          </h3>
          <p className="text-xs text-[#77716A] mb-4">
            Comparison across strategies computed on this video
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#DED7CC] text-[#77716A] font-mono">
                  <th className="py-2.5 px-3 font-medium">Strategy</th>
                  <th className="py-2.5 px-3 font-medium text-right">Frame Reduction</th>
                  <th className="py-2.5 px-3 font-medium text-right">
                    Visual Preservation (Proxy)
                  </th>
                  <th className="py-2.5 px-3 font-medium text-right">
                    Motion Preservation (Proxy)
                  </th>
                  <th className="py-2.5 px-3 font-medium text-right">Compute Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFE8DC]">
                {benchmarkEntries.map(([key, item]) => {
                  const isCurrent = key === currentStrategy;
                  return (
                    <tr
                      key={key}
                      className={isCurrent ? 'bg-[#FDFBF7] font-medium' : 'hover:bg-[#F7F3EC]/50'}
                    >
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5">
                          <span className="capitalize font-semibold text-[#252321]">
                            {key.replace('_', ' ')}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] font-mono uppercase px-1.5 py-0.2 bg-[#D95F32] text-white rounded">
                              Selected
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#D95F32]">
                        {item.frame_reduction_pct.toFixed(1)}%
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#252321]">
                        {item.feature_preservation_index.toFixed(3)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#252321]">
                        {item.motion_preservation_score.toFixed(3)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#77716A]">
                        {item.processing_time_seconds.toFixed(2)}s
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Mandatory Benchmark Disclaimer Box */}
      <div className="rounded-xl border border-[#DED7CC] bg-[#EFE8DC]/50 p-4">
        <div className="flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-[#D95F32]/15 text-[#D95F32] flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-xs font-bold font-mono">!</span>
          </div>
          <div className="text-xs text-[#252321] space-y-1">
            <p className="font-semibold text-[#252321]">
              Visual / Data Preservation Proxy Metrics Disclaimer
            </p>
            <p className="text-[#77716A] leading-relaxed">
              The <strong>Feature Preservation Index</strong> and <strong>Motion Preservation Score</strong> are empirical proxy metrics evaluating mathematical visual similarity (histogram distance) and optical flow energy. They do <em>not</em> represent downstream ML model performance. Never assume downstream accuracy is preserved without evaluating an actual PyTorch model on both datasets. Downstream ML benchmarking is slated for Phase 2.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
