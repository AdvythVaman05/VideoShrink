import React, { useState, useEffect, useCallback, Component, type ErrorInfo, type ReactNode } from 'react';
import { Header } from './components/Header';
import { LandingPage } from './pages/LandingPage';
import { ConfigPage } from './pages/ConfigPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ResultsPage } from './pages/ResultsPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { api, ApiError } from './lib/api';
import { Loader2, AlertCircle, RotateCcw, Download } from 'lucide-react';
import type {
  UploadResponse,
  ProcessRequest,
  ProcessResultsResponse,
} from './types/api';

type AppStage = 'upload' | 'config' | 'processing' | 'results';
type AppTab = 'optimize' | 'experiments';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackJobId?: string | null;
  onReset: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Unhandled render error caught by ErrorBoundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      const jobId = this.props.fallbackJobId;
      return (
        <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-6">
          <div className="w-14 h-14 rounded-full bg-[#FDF2F0] text-[#C24F26] flex items-center justify-center mx-auto border border-[#F5C2B8]">
            <AlertCircle className="w-7 h-7" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-serif font-normal text-[#252321]">
              Display Issue Encountered
            </h2>
            <p className="text-xs font-mono text-[#77716A]">
              {this.state.error?.message || 'An unexpected client error occurred while rendering.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            {jobId && (
              <a
                href={api.getDownloadUrl(jobId)}
                download
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#D95F32] hover:bg-[#C24F26] text-white text-xs font-medium shadow-sm transition-all"
              >
                <Download className="w-4 h-4" />
                <span>Download Optimized Video</span>
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                this.props.onReset();
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-[#DED7CC] bg-[#FFFFFF] hover:bg-[#EFE8DC] text-xs font-medium text-[#252321] transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Return to Upload</span>
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export const App: React.FC = () => {
  const [tab, setTab] = useState<AppTab>('optimize');
  const [stage, setStage] = useState<AppStage>('upload');
  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<ProcessResultsResponse | null>(null);
  const [isLoadingSaved, setIsLoadingSaved] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Restore job status and results from backend using jobId
  const restoreJob = useCallback(async (id: string, preferredStage?: AppStage) => {
    setIsLoadingSaved(true);
    setLoadError(null);
    setJobId(id);
    localStorage.setItem('videoshrink_active_job_id', id);

    try {
      const statusRes = await api.getJobStatus(id);

      if (statusRes.status === 'completed') {
        localStorage.setItem('videoshrink_job_state', 'completed');
        window.location.hash = `#results/${id}`;
        setStage('results');

        // Fetch full results
        const res = await api.getJobResults(id);
        setResults(res);
      } else if (statusRes.status === 'failed') {
        localStorage.setItem('videoshrink_job_state', 'failed');
        window.location.hash = `#processing/${id}`;
        setStage('processing');
      } else if (statusRes.status === 'cancelled') {
        localStorage.setItem('videoshrink_job_state', 'cancelled');
        window.location.hash = `#processing/${id}`;
        setStage('processing');
      } else {
        // 'pending' or 'processing' or 'cancelling'
        localStorage.setItem('videoshrink_job_state', 'processing');
        window.location.hash = `#processing/${id}`;
        setStage('processing');
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        // Stale or deleted job on server (e.g. server restarted)
        console.warn(`Job ${id} not found on server. Clearing stale session.`);
        localStorage.removeItem('videoshrink_active_job_id');
        localStorage.removeItem('videoshrink_job_state');
        if (window.location.hash.includes(id)) {
          window.location.hash = '';
        }
        setJobId(null);
        setResults(null);
        setStage('upload');
      } else {
        // Network or transient server error
        console.error(`Network error restoring job ${id}:`, err);
        setLoadError('Temporary connection error while recovering job.');
        setStage(preferredStage || 'processing');
      }
    } finally {
      setIsLoadingSaved(false);
    }
  }, []);

  // Restore state from URL hash or localStorage on initial load & hash change
  useEffect(() => {
    const handleHash = async () => {
      const hash = window.location.hash;
      if (hash.startsWith('#experiments')) {
        setTab('experiments');
        return;
      }
      setTab('optimize');

      const resultsMatch = hash.match(/^#\/?results\/([a-zA-Z0-9_-]+)/);
      if (resultsMatch) {
        const id = resultsMatch[1];
        await restoreJob(id, 'results');
        return;
      }

      const procMatch = hash.match(/^#\/?processing\/([a-zA-Z0-9_-]+)/);
      if (procMatch) {
        const id = procMatch[1];
        await restoreJob(id, 'processing');
        return;
      }

      // Check localStorage if hash has no job
      const savedJobId = localStorage.getItem('videoshrink_active_job_id');
      if (savedJobId) {
        const savedState = localStorage.getItem('videoshrink_job_state');
        await restoreJob(savedJobId, savedState === 'results' ? 'results' : 'processing');
      }
    };

    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, [restoreJob]);

  const handleUploadSuccess = (data: UploadResponse) => {
    setUploadData(data);
    setStage('config');
  };

  const handleStartProcessing = async (req: ProcessRequest) => {
    const res = await api.startProcessing(req);
    setJobId(res.job_id);
    setResults(null);
    setStage('processing');
    localStorage.setItem('videoshrink_active_job_id', res.job_id);
    localStorage.setItem('videoshrink_job_state', 'processing');
    window.location.hash = `#processing/${res.job_id}`;
  };

  const handleProcessingComplete = async (completedJobId: string) => {
    localStorage.setItem('videoshrink_active_job_id', completedJobId);
    localStorage.setItem('videoshrink_job_state', 'completed');
    window.location.hash = `#results/${completedJobId}`;
    setStage('results');
    setLoadError(null);

    // Fetch results with resilient retry logic
    let attempts = 0;
    while (attempts < 3) {
      try {
        const res = await api.getJobResults(completedJobId);
        setResults(res);
        return;
      } catch (err) {
        attempts++;
        if (attempts >= 3) {
          console.error('Failed to fetch completed job results after 3 attempts:', err);
          setLoadError('Failed to load processing results. Please click Retry.');
        } else {
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
    }
  };

  const handleReset = () => {
    localStorage.removeItem('videoshrink_active_job_id');
    localStorage.removeItem('videoshrink_job_state');
    window.location.hash = '';
    setUploadData(null);
    setJobId(null);
    setResults(null);
    setLoadError(null);
    setStage('upload');
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F3EC] text-[#252321] selection:bg-[#D95F32]/20 selection:text-[#D95F32]">
      <Header
        currentTab={tab}
        onSelectTab={(selectedTab) => {
          setTab(selectedTab);
          if (selectedTab === 'experiments') {
            window.location.hash = '#experiments';
          } else if (selectedTab === 'optimize') {
            if (stage === 'results' && jobId) {
              window.location.hash = `#results/${jobId}`;
            } else if (stage === 'processing' && jobId) {
              window.location.hash = `#processing/${jobId}`;
            } else {
              window.location.hash = '';
            }
          }
        }}
      />

      <main className="flex-1">
        <ErrorBoundary fallbackJobId={jobId} onReset={handleReset}>
          {isLoadingSaved ? (
            <div className="flex flex-col items-center justify-center py-28 space-y-3">
              <Loader2 className="w-7 h-7 text-[#D95F32] animate-spin" />
              <p className="text-xs font-mono text-[#77716A]">Restoring compression session...</p>
            </div>
          ) : tab === 'experiments' ? (
            <ExperimentsPage
              onNewRun={() => {
                setTab('optimize');
                handleReset();
              }}
            />
          ) : (
            <>
              {stage === 'upload' && (
                <LandingPage onUploadSuccess={handleUploadSuccess} />
              )}

              {stage === 'config' && uploadData && (
                <ConfigPage
                  uploadData={uploadData}
                  onStartProcessing={handleStartProcessing}
                  onReset={handleReset}
                />
              )}

              {stage === 'processing' && jobId && (
                <ProcessingPage
                  jobId={jobId}
                  onCompleted={handleProcessingComplete}
                  onFailed={(err) => {
                    console.error('Processing job failed:', err);
                  }}
                  onCancel={() => {
                    localStorage.removeItem('videoshrink_active_job_id');
                    localStorage.removeItem('videoshrink_job_state');
                    window.location.hash = '';
                    if (uploadData) {
                      setStage('config');
                    } else {
                      handleReset();
                    }
                  }}
                  onStaleJob={handleReset}
                />
              )}

              {stage === 'results' && (
                results ? (
                  <ResultsPage
                    results={results}
                    originalMetadata={uploadData?.metadata}
                    onStartOver={handleReset}
                  />
                ) : (
                  <div className="max-w-xl mx-auto px-4 py-24 text-center space-y-4">
                    {loadError ? (
                      <div className="p-6 rounded-2xl bg-[#FDF2F0] border border-[#F5C2B8] text-center space-y-4">
                        <AlertCircle className="w-8 h-8 text-[#C24F26] mx-auto" />
                        <h3 className="text-base font-semibold text-[#252321]">Unable to load results</h3>
                        <p className="text-xs text-[#77716A]">{loadError}</p>
                        <div className="flex justify-center gap-3 pt-2">
                          <button
                            type="button"
                            onClick={() => jobId && handleProcessingComplete(jobId)}
                            className="px-4 py-2 rounded-xl bg-[#D95F32] text-white text-xs font-medium hover:bg-[#C24F26] cursor-pointer"
                          >
                            Retry
                          </button>
                          <button
                            type="button"
                            onClick={handleReset}
                            className="px-4 py-2 rounded-xl bg-white border border-[#DED7CC] text-xs font-medium hover:bg-[#EFE8DC] cursor-pointer"
                          >
                            Start Over
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center space-y-3">
                        <Loader2 className="w-8 h-8 text-[#D95F32] animate-spin" />
                        <p className="text-sm font-serif text-[#252321]">Finalizing results...</p>
                        <p className="text-xs font-mono text-[#77716A]">Compiling visual proxy metrics and video streams</p>
                      </div>
                    )}
                  </div>
                )
              )}
            </>
          )}
        </ErrorBoundary>
      </main>

      <footer className="border-t border-[#DED7CC] bg-[#FFFFFF] py-6 mt-12 text-center text-xs text-[#77716A]">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="font-mono">
            <span>VideoShrink</span> • <span>Information-Preserving Dataset Pruning</span>
          </div>
          <div className="font-mono text-[11px] text-[#A29A90]">
            Proxy Metrics evaluate visual & motion continuity • Downstream PyTorch ML evaluation in Phase 2
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;

