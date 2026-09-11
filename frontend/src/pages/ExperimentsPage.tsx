import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { formatPercentage } from '../lib/utils';
import type { ExperimentSummary } from '../types/api';
import { History, Download, RefreshCw, Database, ArrowRight, Loader2 } from 'lucide-react';

interface ExperimentsPageProps {
  onNewRun: () => void;
}

export const ExperimentsPage: React.FC<ExperimentsPageProps> = ({ onNewRun }) => {
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchExperiments = async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const res = await api.getExperiments();
      setExperiments(res.experiments || []);
    } catch (err) {
      setErrorMessage('Failed to load experiments history from database.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExperiments();
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#DED7CC] pb-6">
        <div>
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-[#D95F32]" />
            <h1 className="text-2xl sm:text-3xl font-serif font-normal text-[#252321]">
              Experiment History
            </h1>
          </div>
          <p className="text-xs text-[#77716A] mt-1">
            Persisted runs stored in SQLite experiment tracking database
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchExperiments}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] hover:bg-[#EFE8DC] text-xs font-medium text-[#252321] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#D95F32]' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={onNewRun}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#D95F32] hover:bg-[#C24F26] text-white text-xs font-medium shadow-xs transition-colors"
          >
            <span>New Compression</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-[#FDF2F0] border border-[#F5C2B8] text-[#C24F26] text-xs">
          {errorMessage}
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-[#D95F32]" />
          <p className="text-xs font-mono text-[#77716A]">Querying SQLite experiment records...</p>
        </div>
      ) : experiments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#DED7CC] bg-[#FFFFFF] p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-[#EFE8DC] text-[#77716A] flex items-center justify-center mx-auto">
            <Database className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-base text-[#252321]">
            No experiments recorded yet
          </h3>
          <p className="text-xs text-[#77716A] max-w-sm mx-auto">
            Run a compression job on an uploaded or sample video to automatically log parameters, metrics, and timestamps.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={onNewRun}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#D95F32] text-white text-xs font-medium"
            >
              Start First Compression
            </button>
          </div>
        </div>
      ) : (
        /* Experiments Table */
        <div className="rounded-2xl border border-[#DED7CC] bg-[#FFFFFF] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#DED7CC] bg-[#F7F3EC] text-[#77716A] font-mono">
                  <th className="py-3 px-4 font-medium">Timestamp</th>
                  <th className="py-3 px-4 font-medium">File</th>
                  <th className="py-3 px-4 font-medium">Strategy</th>
                  <th className="py-3 px-4 font-medium">Parameters</th>
                  <th className="py-3 px-4 font-medium text-right">Frame Red.</th>
                  <th className="py-3 px-4 font-medium text-right">Size Red.</th>
                  <th className="py-3 px-4 font-medium text-right">Proxy Fidelity</th>
                  <th className="py-3 px-4 font-medium text-right">Duration</th>
                  <th className="py-3 px-4 font-medium text-center">Export</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFE8DC]">
                {experiments.map((exp) => {
                  const paramStr = Object.entries(exp.parameters || {})
                    .map(([k, v]) => `${k}=${v}`)
                    .join(', ');

                  return (
                    <tr key={exp.experiment_id} className="hover:bg-[#FDFBF7] transition-colors">
                      <td className="py-3 px-4 font-mono text-[#77716A] whitespace-nowrap">
                        {new Date(exp.timestamp).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="py-3 px-4 font-medium text-[#252321] max-w-[150px] truncate" title={exp.filename}>
                        {exp.filename}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono font-medium capitalize bg-[#EFE8DC] text-[#252321]">
                          {exp.strategy.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#77716A] max-w-[140px] truncate" title={paramStr}>
                        {paramStr || 'default'}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-medium text-[#D95F32]">
                        {formatPercentage(exp.frame_reduction_pct)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-[#252321]">
                        {formatPercentage(exp.file_size_reduction_pct)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-[#252321]">
                        {exp.feature_preservation_index.toFixed(3)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-[#77716A]">
                        {exp.processing_time_seconds.toFixed(2)}s
                      </td>
                      <td className="py-3 px-4 text-center">
                        <a
                          href={api.getExperimentExportUrl(exp.experiment_id)}
                          download={`experiment_${exp.experiment_id}.json`}
                          className="inline-flex items-center justify-center p-1.5 rounded-lg border border-[#DED7CC] text-[#77716A] hover:text-[#D95F32] hover:border-[#D95F32] transition-colors"
                          title="Export Experiment JSON"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
