import React, { useEffect, useState } from 'react';
import { Loader2, AlertCircle, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { api } from '../lib/api';
import type { JobStatusResponse } from '../types/api';

interface ProcessingPageProps {
  jobId: string;
  onCompleted: (jobId: string) => void;
  onFailed: (error: string) => void;
  onCancel: () => void;
}

export const ProcessingPage: React.FC<ProcessingPageProps> = ({
  jobId,
  onCompleted,
  onFailed,
  onCancel,
}) => {
  const [status, setStatus] = useState<JobStatusResponse>({
    job_id: jobId,
    status: 'pending',
    progress: 0.05,
    current_step: 'Initializing compression job...',
    error_message: null,
  });

  useEffect(() => {
    let isMounted = true;
    let pollInterval: ReturnType<typeof setInterval>;

    const checkStatus = async () => {
      try {
        const res = await api.getJobStatus(jobId);
        if (!isMounted) return;

        setStatus(res);

        if (res.status === 'completed') {
          clearInterval(pollInterval);
          setTimeout(() => {
            if (isMounted) onCompleted(jobId);
          }, 600);
        } else if (res.status === 'failed') {
          clearInterval(pollInterval);
          onFailed(res.error_message || 'Video processing failed.');
        }
      } catch (err) {
        if (!isMounted) return;
        // Keep polling briefly in case of transient network hiccup
      }
    };

    checkStatus();
    pollInterval = setInterval(checkStatus, 1000);

    return () => {
      isMounted = false;
      clearInterval(pollInterval);
    };
  }, [jobId, onCompleted, onFailed]);

  const percent = Math.min(
    100,
    Math.max(0, Math.round(status.progress > 1 ? status.progress : status.progress * 100))
  );

  return (
    <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-8">
      <div className="w-16 h-16 rounded-full bg-[#EFE8DC] text-[#D95F32] flex items-center justify-center mx-auto">
        {status.status === 'completed' ? (
          <CheckCircle2 className="w-8 h-8 text-[#1E7E34]" />
        ) : status.status === 'failed' ? (
          <AlertCircle className="w-8 h-8 text-[#C24F26]" />
        ) : (
          <Loader2 className="w-8 h-8 animate-spin" />
        )}
      </div>

      <div className="space-y-2">
        <h2 className="text-2xl font-serif font-normal text-[#252321]">
          {status.status === 'completed'
            ? 'Optimization Finalized'
            : status.status === 'failed'
            ? 'Processing Interrupted'
            : 'Analyzing & Compressing Sequence'}
        </h2>
        <p className="text-sm font-mono text-[#D95F32]">
          {status.current_step || 'Evaluating frames...'}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="h-2.5 w-full bg-[#EFE8DC] rounded-full overflow-hidden border border-[#DED7CC]">
          <div
            className="h-full bg-[#D95F32] transition-all duration-500 ease-out"
            style={{ width: `${Math.max(5, percent)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs font-mono text-[#77716A]">
          <span>Job: {jobId.slice(0, 8)}...</span>
          <span>{percent}%</span>
        </div>
      </div>

      {/* Failure Info */}
      {status.status === 'failed' && (
        <div className="p-4 rounded-xl bg-[#FDF2F0] border border-[#F5C2B8] text-[#C24F26] text-xs text-left">
          <p className="font-semibold mb-1">Error Encountered:</p>
          <p>{status.error_message || 'Unknown processing error.'}</p>
          <button
            type="button"
            onClick={onCancel}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-[#F5C2B8] text-xs font-medium text-[#C24F26] hover:bg-[#FDF2F0]"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to configuration</span>
          </button>
        </div>
      )}

      {/* Subtext */}
      <p className="text-xs text-[#77716A] max-w-sm mx-auto">
        Running frame-by-frame color/gradient histogram diffing, optical flow calculations, and multi-threaded video encoding.
      </p>
    </div>
  );
};
