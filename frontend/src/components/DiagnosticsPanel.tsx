import React from 'react';
import { ShieldCheck, AlertTriangle, AlertCircle, Award, CheckCircle2, Activity } from 'lucide-react';
import type { FailureAnalysis, VisualPreservationProxyResult, BenchmarkResult } from '../types/api';

interface DiagnosticsPanelProps {
  failureAnalysis?: FailureAnalysis;
  benchmark?: VisualPreservationProxyResult | Record<string, BenchmarkResult>;
  currentStrategy: string;
}

export const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({
  failureAnalysis,
  benchmark,
  currentStrategy,
}) => {
  const segments = failureAnalysis?.segments || [];
  const segmentCount = failureAnalysis?.sensitive_segments_count ?? segments.length;

  const hasHighSeverity = segments.some((s) => s.severity === 'high') || failureAnalysis?.information_loss_risk === 'high';
  const hasMediumSeverity = segments.some((s) => s.severity === 'medium') || failureAnalysis?.information_loss_risk === 'medium' || segmentCount > 0;

  const riskBadge = hasHighSeverity ? (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#FDF2F0] text-[#C24F26] border border-[#F5C2B8]">
      <AlertCircle className="w-3.5 h-3.5" /> High Information Loss
    </span>
  ) : hasMediumSeverity ? (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#FFF8E6] text-[#B7791F] border border-[#FEEBAA]">
      <AlertTriangle className="w-3.5 h-3.5" /> Moderate Risk ({segmentCount} segments)
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#EBF5EE] text-[#1E7E34] border border-[#C3E6CB]">
      <ShieldCheck className="w-3.5 h-3.5" /> Low Risk (0 segments)
    </span>
  );

  // Check whether benchmark is a single VisualPreservationProxyResult or a comparison map
  const isProxyResult = benchmark && 'proxy_fidelity_score' in benchmark;
  const proxyBenchmark = isProxyResult ? (benchmark as VisualPreservationProxyResult) : null;
  const multiBenchmarkEntries = (!isProxyResult && benchmark)
    ? Object.entries(benchmark as Record<string, BenchmarkResult>)
    : [];

  return (
    <div className="space-y-6">
      {/* Risk and Quality Diagnostics Card */}
      <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-base text-[#252321]">
              Quality Diagnostics & Sensitive Segments
            </h3>
            <p className="text-xs text-[#77716A]">
              Automated heuristics evaluating temporal continuity, abrupt motion, and pruning risks
            </p>
          </div>
          <div>{riskBadge}</div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <div className="p-3.5 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
            <div className="text-xs text-[#77716A] font-medium mb-1">
              Sensitive Segment Count
            </div>
            <div className="text-2xl font-mono font-semibold text-[#252321]">
              {segmentCount}
            </div>
            <p className="text-[11px] text-[#77716A] mt-1">
              {segmentCount === 0
                ? 'No abrupt scene transitions or unrepresented motion bursts.'
                : 'Clustered intervals with high motion, rapid camera pan, or scene cuts.'}
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
            <div className="text-xs text-[#77716A] font-medium mb-1">
              Temporal Continuity State
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-mono font-semibold text-[#252321]">
                {segmentCount === 0 ? 'Optimal' : 'Monitored'}
              </span>
              {segmentCount === 0 ? (
                <CheckCircle2 className="w-5 h-5 text-[#1E7E34]" />
              ) : (
                <Activity className="w-5 h-5 text-[#D95F32]" />
              )}
            </div>
            <p className="text-[11px] text-[#77716A] mt-1">
              Continuous chronological frame retention without perceptual blind spots.
            </p>
          </div>
        </div>

        {/* Sensitive Segments Breakdown */}
        {segments.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[#EFE8DC] space-y-2">
            <h4 className="text-xs font-semibold text-[#252321] uppercase tracking-wider font-mono">
              Detected Sensitive Segments
            </h4>
            <div className="space-y-2">
              {segments.map((seg, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl border text-xs ${
                    seg.severity === 'high'
                      ? 'bg-[#FDF2F0] border-[#F5C2B8] text-[#C24F26]'
                      : 'bg-[#FFF8E6] border-[#FEEBAA] text-[#B7791F]'
                  }`}
                >
                  <div className="flex items-center justify-between font-mono font-semibold mb-1">
                    <span>
                      {seg.start_time_formatted} - {seg.end_time_formatted} ({((seg.end_sec - seg.start_sec) || 0).toFixed(1)}s)
                    </span>
                    <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-white/70">
                      {seg.severity} severity
                    </span>
                  </div>
                  <div className="text-xs text-[#252321]">{seg.reasons?.join(' • ')}</div>
                  {seg.recommendation && (
                    <div className="text-[11px] text-[#77716A] mt-1">
                      💡 {seg.recommendation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warnings & Recommendations */}
        {((failureAnalysis?.warnings?.length ?? 0) > 0 || (failureAnalysis?.recommendations?.length ?? 0) > 0) && (
          <div className="mt-4 pt-4 border-t border-[#EFE8DC] space-y-2">
            {failureAnalysis?.warnings?.map((warning, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs text-[#C24F26] bg-[#FDF2F0] p-2.5 rounded-lg border border-[#F5C2B8]"
              >
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{warning}</span>
              </div>
            ))}
            {failureAnalysis?.recommendations?.map((rec, i) => (
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

      {/* Visual Preservation Proxy Breakdown (Single Strategy Run) */}
      {proxyBenchmark && (
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] p-5 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-base text-[#252321]">
              Visual / Data Preservation Proxy Analysis
            </h3>
            <span className="text-xs font-mono uppercase tracking-wider text-[#D95F32] font-semibold">
              {currentStrategy.replace('_', ' ')}
            </span>
          </div>
          <p className="text-xs text-[#77716A] mb-4">
            Deterministic spatial and temporal heuristics measuring visual retention
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
              <div className="text-[11px] text-[#77716A] font-medium">Proxy Fidelity</div>
              <div className="text-xl font-mono font-semibold text-[#D95F32] mt-0.5">
                {(proxyBenchmark.proxy_fidelity_score ?? 0).toFixed(3)}
              </div>
              <div className="text-[10px] text-[#77716A] mt-0.5">Overall composite</div>
            </div>

            <div className="p-3 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
              <div className="text-[11px] text-[#77716A] font-medium">Motion Coverage</div>
              <div className="text-xl font-mono font-semibold text-[#252321] mt-0.5">
                {((proxyBenchmark.motion_coverage_score ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] text-[#77716A] mt-0.5">Peak motion sampled</div>
            </div>

            <div className="p-3 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
              <div className="text-[11px] text-[#77716A] font-medium">Temporal Uniformity</div>
              <div className="text-xl font-mono font-semibold text-[#252321] mt-0.5">
                {((proxyBenchmark.temporal_coverage_score ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] text-[#77716A] mt-0.5">Even distribution</div>
            </div>

            <div className="p-3 rounded-xl bg-[#F7F3EC] border border-[#DED7CC]">
              <div className="text-[11px] text-[#77716A] font-medium">Sharpness Ratio</div>
              <div className="text-xl font-mono font-semibold text-[#252321] mt-0.5">
                {((proxyBenchmark.sharpness_preservation_ratio ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] text-[#77716A] mt-0.5">Sharp frames kept</div>
            </div>
          </div>
        </div>
      )}

      {/* Multi-Strategy Benchmark Comparison Table (if comparative data available) */}
      {multiBenchmarkEntries.length > 0 && (
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
                {multiBenchmarkEntries.map(([key, item]) => {
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
                        {(item.frame_reduction_pct ?? 0).toFixed(1)}%
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#252321]">
                        {(item.feature_preservation_index ?? 0).toFixed(3)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#252321]">
                        {(item.motion_preservation_score ?? 0).toFixed(3)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#77716A]">
                        {(item.processing_time_seconds ?? 0).toFixed(2)}s
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
              {proxyBenchmark?.disclaimer || (
                <>
                  The <strong>Feature Preservation Index</strong> and <strong>Motion Preservation Score</strong> are empirical proxy metrics evaluating mathematical visual similarity (histogram distance) and optical flow energy. They do <em>not</em> represent downstream ML model performance. Never assume downstream accuracy is preserved without evaluating an actual vision model on both datasets. Downstream ML benchmarking is slated for Phase 2.
                </>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
