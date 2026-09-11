import React, { useState, useEffect, Component, type ErrorInfo, type ReactNode } from 'react';
import { Header } from './components/Header';
import { LandingPage } from './pages/LandingPage';
import { ConfigPage } from './pages/ConfigPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ResultsPage } from './pages/ResultsPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { api } from './lib/api';
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
        setJobId(id);
        setStage('results');
        setIsLoadingSaved(true);
        try {
          const res = await api.getJobResults(id);
          setResults(res);
          localStorage.setItem('videoshrink_active_job_id', id);
        } catch (e) {
          console.error('Failed to restore job results from hash:', e);
        } finally {
          setIsLoadingSaved(false);
        }
        return;
      }

      const procMatch = hash.match(/^#\/?processing\/([a-zA-Z0-9_-]+)/);
      if (procMatch) {
        const id = procMatch[1];
        setJobId(id);
        setStage('processing');
        return;
      }

      // Check localStorage if hash has no job
      const savedJobId = localStorage.getItem('videoshrink_active_job_id');
      if (savedJobId && stage === 'upload' && !results) {
        setIsLoadingSaved(true);
        try {
          const res = await api.getJobResults(savedJobId);
          if (res && res.metrics) {
            setJobId(savedJobId);
            setResults(res);
            setStage('results');
            window.location.hash = `#results/${savedJobId}`;
          }
        } catch {
          localStorage.removeItem('videoshrink_active_job_id');
        } finally {
          setIsLoadingSaved(false);
        }
      }
    };

    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const handleUploadSuccess = (data: UploadResponse) => {
    setUploadData(data);
    setStage('config');
  };

  const handleStartProcessing = async (req: ProcessRequest) => {
    const res = await api.startProcessing(req);
    setJobId(res.job_id);
    setStage('processing');
    localStorage.setItem('videoshrink_active_job_id', res.job_id);
    window.location.hash = `#processing/${res.job_id}`;
  };

  const handleProcessingComplete = async (completedJobId: string) => {
    try {
      const res = await api.getJobResults(completedJobId);
      setResults(res);
      setStage('results');
      localStorage.setItem('videoshrink_active_job_id', completedJobId);
      window.location.hash = `#results/${completedJobId}`;
    } catch (err) {
      console.error('Failed to fetch completed job results:', err);
    }
  };

  const handleReset = () => {
    localStorage.removeItem('videoshrink_active_job_id');
    window.location.hash = '';
    setUploadData(null);
    setJobId(null);
    setResults(null);
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
          } else if (stage === 'results' && jobId) {
            window.location.hash = `#results/${jobId}`;
          } else {
            window.location.hash = '';
          }
        }}
      />

      <main className="flex-1">
        <ErrorBoundary fallbackJobId={jobId} onReset={handleReset}>
          {isLoadingSaved ? (
            <div className="flex flex-col items-center justify-center py-28 space-y-3">
              <Loader2 className="w-7 h-7 text-[#D95F32] animate-spin" />
              <p className="text-xs font-mono text-[#77716A]">Loading compression results...</p>
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
                  onCancel={() => setStage('config')}
                />
              )}

              {stage === 'results' && results && (
                <ResultsPage
                  results={results}
                  originalMetadata={uploadData?.metadata}
                  onStartOver={handleReset}
                />
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

