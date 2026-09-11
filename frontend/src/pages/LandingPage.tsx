import React from 'react';
import { UploadDropzone } from '../components/UploadDropzone';
import type { UploadResponse } from '../types/api';
import { Layers, Zap, Database } from 'lucide-react';

interface LandingPageProps {
  onUploadSuccess: (data: UploadResponse) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onUploadSuccess }) => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-16 space-y-16">
      {/* Hero Section */}
      <div className="text-center space-y-4 max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#EFE8DC] border border-[#DED7CC] text-xs font-mono text-[#D95F32] font-medium">
          <span>Production-Quality CV Preprocessing</span>
        </div>

        <h1 className="text-4xl sm:text-5xl font-serif font-normal tracking-tight text-[#252321] leading-tight">
          Smarter video datasets.<br />
          <span className="italic font-normal text-[#D95F32]">Less redundant compute.</span>
        </h1>

        <p className="text-sm sm:text-base text-[#77716A] leading-relaxed max-w-xl mx-auto">
          Intelligently prune visually redundant frames from video datasets while preserving vital motion and scene context. Cut training storage and token processing costs.
        </p>
      </div>

      {/* Upload Dropzone Container */}
      <UploadDropzone onUploadSuccess={onUploadSuccess} />

      {/* 3 Technical Value Props */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-[#DED7CC]">
        <div className="space-y-2">
          <div className="w-8 h-8 rounded-lg bg-[#EFE8DC] flex items-center justify-center text-[#D95F32]">
            <Layers className="w-4 h-4" />
          </div>
          <h3 className="font-semibold text-sm text-[#252321]">
            Perceptual Cosine Similarity
          </h3>
          <p className="text-xs text-[#77716A] leading-relaxed">
            Measures HSV color distribution and Sobel edge gradients to identify and discard near-duplicate frames.
          </p>
        </div>

        <div className="space-y-2">
          <div className="w-8 h-8 rounded-lg bg-[#EFE8DC] flex items-center justify-center text-[#D95F32]">
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="font-semibold text-sm text-[#252321]">
            Motion-Aware Optical Flow
          </h3>
          <p className="text-xs text-[#77716A] leading-relaxed">
            Tracks Farneback vector fields to ensure rapid actions, camera pans, and critical transitions are faithfully retained.
          </p>
        </div>

        <div className="space-y-2">
          <div className="w-8 h-8 rounded-lg bg-[#EFE8DC] flex items-center justify-center text-[#D95F32]">
            <Database className="w-4 h-4" />
          </div>
          <h3 className="font-semibold text-sm text-[#252321]">
            ML Pipeline Extensibility
          </h3>
          <p className="text-xs text-[#77716A] leading-relaxed">
            Built as a modular preprocessing filter ready to integrate directly with PyTorch, OpenCV, or video dataloaders.
          </p>
        </div>
      </div>
    </div>
  );
};
