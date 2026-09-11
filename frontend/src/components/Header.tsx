import React from 'react';
import { Film, History, Sparkles } from 'lucide-react';

interface HeaderProps {
  currentTab: 'optimize' | 'experiments';
  onSelectTab: (tab: 'optimize' | 'experiments') => void;
}

export const Header: React.FC<HeaderProps> = ({ currentTab, onSelectTab }) => {
  return (
    <header className="border-b border-[#DED7CC] bg-[#FFFFFF]/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div 
          onClick={() => onSelectTab('optimize')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-9 h-9 rounded-lg bg-[#D95F32] flex items-center justify-center text-white shadow-sm transition-transform group-hover:scale-105">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-lg tracking-tight text-[#252321]">
                VideoShrink
              </span>
              <span className="text-[11px] font-mono uppercase px-1.5 py-0.5 rounded bg-[#EFE8DC] text-[#77716A] border border-[#DED7CC]/60 font-medium">
                v1.0
              </span>
            </div>
            <p className="text-xs text-[#77716A] hidden sm:block">
              Information-Preserving Dataset Compression
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 bg-[#EFE8DC]/80 p-1 rounded-lg border border-[#DED7CC]/70">
          <button
            onClick={() => onSelectTab('optimize')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              currentTab === 'optimize'
                ? 'bg-white text-[#252321] shadow-xs'
                : 'text-[#77716A] hover:text-[#252321]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Compressor</span>
          </button>
          <button
            onClick={() => onSelectTab('experiments')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              currentTab === 'experiments'
                ? 'bg-white text-[#252321] shadow-xs'
                : 'text-[#77716A] hover:text-[#252321]'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Experiments</span>
          </button>
        </div>

        {/* External links */}
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/AdvythVaman05/VideoShrink"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-medium text-[#77716A] hover:text-[#252321] px-2.5 py-1.5 rounded-md hover:bg-[#EFE8DC] transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span className="hidden md:inline">GitHub</span>
          </a>
        </div>
      </div>
    </header>
  );
};
