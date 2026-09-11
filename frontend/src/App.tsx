import React, { useState } from 'react';
import { Header } from './components/Header';
import { LandingPage } from './pages/LandingPage';
import { ConfigPage } from './pages/ConfigPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ResultsPage } from './pages/ResultsPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { api } from './lib/api';
import type {
  UploadResponse,
  ProcessRequest,
  ProcessResultsResponse,
} from './types/api';

type AppStage = 'upload' | 'config' | 'processing' | 'results';
type AppTab = 'optimize' | 'experiments';

export const App: React.FC = () => {
  const [tab, setTab] = useState<AppTab>('optimize');
  const [stage, setStage] = useState<AppStage>('upload');
  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<ProcessResultsResponse | null>(null);

  const handleUploadSuccess = (data: UploadResponse) => {
    setUploadData(data);
    setStage('config');
  };

  const handleStartProcessing = async (req: ProcessRequest) => {
    const res = await api.startProcessing(req);
    setJobId(res.job_id);
    setStage('processing');
  };

  const handleProcessingComplete = async (completedJobId: string) => {
    const res = await api.getJobResults(completedJobId);
    setResults(res);
    setStage('results');
  };

  const handleReset = () => {
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
        }}
      />

      <main className="flex-1">
        {tab === 'experiments' ? (
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
