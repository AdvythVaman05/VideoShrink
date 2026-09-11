import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Loader2, AlertCircle, ArrowLeft, CheckCircle2, WifiOff, XCircle } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import type { JobStatusResponse } from '../types/api';

interface ProcessingPageProps {
  jobId: string;
  onCompleted: (jobId: string) => void;
  onFailed: (error: string) => void;
  onCancel: () => void;
  onStaleJob?: () => void;
}

export const ProcessingPage: React.FC<ProcessingPageProps> = ({
  jobId,
  onCompleted,
  onFailed,
  onCancel,
  onStaleJob,
}) => {
  const [status, setStatus] = useState<JobStatusResponse>({
    job_id: jobId,
    status: 'pending',
    progress: 0.05,
    current_step: 'Initializing compression job...',
    error_message: null,
  });
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const isMountedRef = useRef(true);
  const isCheckingRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkStatus = useCallback(async () => {
    if (isCheckingRef.current || !isMountedRef.current) return;
    isCheckingRef.current = true;

    try {
      const res = await api.getJobStatus(jobId);
      if (!isMountedRef.current) return;

      setStatus(res);
      setIsReconnecting(false);

      if (res.status === 'completed') {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        onCompleted(jobId);
      } else if (res.status === 'failed') {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        onFailed(res.error_message || 'Video processing failed.');
      } else if (res.status === 'cancelled') {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        setIsCancelling(false);
      }
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      if (err instanceof ApiError && err.status === 404) {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        if (onStaleJob) {
          onStaleJob();
        } else {
          onFailed(`Processing job '${jobId}' was not found on server.`);
        }
        return;
      }

      // Temporary network error or server hiccup
      setIsReconnecting(true);
    } finally {
      isCheckingRef.current = false;
    }
  }, [jobId, onCompleted, onFailed, onStaleJob]);

  const handleCancelClick = async () => {
    const confirmed = window.confirm('Cancel processing? The current processing job will be stopped.');
    if (!confirmed) return;

    setIsCancelling(true);
    setCancelError(null);

    try {
      await api.cancelJob(jobId);
      await checkStatus();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        // Job completed or failed just before cancellation
        await checkStatus();
      } else {
        setCancelError(err instanceof Error ? err.message : 'Failed to request cancellation.');
        setIsCancelling(false);
      }
    }
  };

  useEffect(() => {
    isMountedRef.current = true;

    // 1. Immediately poll status on mount
    checkStatus();

    // 2. Set up regular polling interval (1500ms)
    pollTimerRef.current = setInterval(() => {
      if (!document.hidden) {
        checkStatus();
      }
    }, 1500);

    // 3. Tab switching & window focus handlers:
    // When the browser tab becomes active again, immediately poll without waiting for interval
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        checkStatus();
      }
    };

    const handleFocus = () => {
      checkStatus();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    return () => {
      isMountedRef.current = false;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [checkStatus]);

  const percent = Math.min(
    100,
    Math.max(0, Math.round(status.progress > 1 ? status.progress : status.progress * 100))
  );

  const isTerminalCancelled = status.status === 'cancelled';
  const isCancellingActive = isCancelling || status.status === 'cancelling';

  return (
    <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-8">
      {/* Reconnecting banner if network drops */}
      {isReconnecting && (
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#FFF8E6] border border-[#FEEBAA] text-[#B7791F] text-xs font-mono animate-pulse">
          <WifiOff className="w-3.5 h-3.5 shrink-0" />
          <span>Connection hiccup — reconnecting to background job...</span>
        </div>
      )}

      <div className="w-16 h-16 rounded-full bg-[#EFE8DC] text-[#D95F32] flex items-center justify-center mx-auto">
        {status.status === 'completed' ? (
          <CheckCircle2 className="w-8 h-8 text-[#1E7E34]" />
        ) : isTerminalCancelled ? (
          <XCircle className="w-8 h-8 text-[#77716A]" />
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
            : isTerminalCancelled
            ? 'Processing Cancelled'
            : status.status === 'failed'
            ? 'Processing Interrupted'
            : isCancellingActive
            ? 'Cancelling Processing...'
            : 'Analyzing & Compressing Sequence'}
        </h2>
        <p className="text-sm font-mono text-[#D95F32]">
          {isTerminalCancelled
            ? 'Job stopped by user. Incomplete output removed.'
            : isCancellingActive
            ? 'Terminating background tasks and cleaning up files...'
            : status.current_step || 'Evaluating frames...'}
        </p>
      </div>

      {/* Progress Bar (hidden if cancelled) */}
      {!isTerminalCancelled && (
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
      )}

      {/* Cancelled State Card */}
      {isTerminalCancelled && (
        <div className="p-6 rounded-2xl bg-[#FFFFFF] border border-[#DED7CC] text-center space-y-4 shadow-sm">
          <p className="text-xs font-mono text-[#77716A]">
            Background worker stopped cooperatively. Temporary files and partial MP4 streams were deleted.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-white border border-[#DED7CC] text-xs font-medium text-[#252321] hover:bg-[#EFE8DC] cursor-pointer shadow-sm transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Return to Configuration</span>
            </button>
          </div>
        </div>
      )}

      {/* Cancel Processing Action during active processing */}
      {(status.status === 'pending' || status.status === 'processing' || isCancellingActive) && !isTerminalCancelled && (
        <div className="pt-2 flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={handleCancelClick}
            disabled={isCancellingActive}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white border border-[#F5C2B8] text-xs font-medium text-[#C24F26] hover:bg-[#FDF2F0] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors shadow-sm"
          >
            {isCancellingActive ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Cancelling...</span>
              </>
            ) : (
              <span>Cancel Processing</span>
            )}
          </button>
          {cancelError && (
            <p className="text-xs text-[#C24F26] font-mono">{cancelError}</p>
          )}
        </div>
      )}

      {/* Failure Info */}
      {status.status === 'failed' && (
        <div className="p-4 rounded-xl bg-[#FDF2F0] border border-[#F5C2B8] text-[#C24F26] text-xs text-left">
          <p className="font-semibold mb-1">Error Encountered:</p>
          <p>{status.error_message || 'Unknown processing error.'}</p>
          <button
            type="button"
            onClick={onCancel}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-[#F5C2B8] text-xs font-medium text-[#C24F26] hover:bg-[#FDF2F0] cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to configuration</span>
          </button>
        </div>
      )}

      {/* Subtext */}
      {!isTerminalCancelled && (
        <p className="text-xs text-[#77716A] max-w-sm mx-auto">
          Running frame-by-frame color/gradient histogram diffing, optical flow calculations, and multi-threaded video encoding in background worker.
        </p>
      )}
    </div>
  );
};
