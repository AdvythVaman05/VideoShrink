import React, { useState, useRef } from 'react';
import { UploadCloud, PlayCircle, AlertCircle, Loader2 } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import type { UploadResponse } from '../types/api';

interface UploadDropzoneProps {
  onUploadSuccess: (data: UploadResponse) => void;
}

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setErrorMessage(null);
    const validExtensions = ['.mp4', '.mov', '.avi', '.webm', '.mkv'];
    const hasValidExt = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    );

    if (!hasValidExt) {
      setErrorMessage('Please select a supported video file (.mp4, .mov, .avi, .webm, .mkv)');
      return;
    }

    if (file.size > 200 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 200 MB maximum limit for MVP processing.');
      return;
    }

    try {
      setIsUploading(true);
      const res = await api.uploadVideo(file);
      onUploadSuccess(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(`Upload failed (${err.status}): ${err.message}`);
      } else {
        setErrorMessage('Failed to upload video. Please check your connection and try again.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSampleClick = async () => {
    setErrorMessage(null);
    try {
      setIsLoadingSample(true);
      const res = await api.loadSampleVideo();
      onUploadSuccess(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(`Sample loading failed: ${err.message}`);
      } else {
        setErrorMessage('Could not load the benchmark sample video.');
      }
    } finally {
      setIsLoadingSample(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && !isLoadingSample && fileInputRef.current?.click()}
        className={`group relative rounded-2xl border-2 border-dashed p-10 text-center transition-all cursor-pointer bg-[#FFFFFF] ${
          isDragging
            ? 'border-[#D95F32] bg-[#D95F32]/5 shadow-md'
            : 'border-[#DED7CC] hover:border-[#D95F32]/60 hover:bg-[#FDFBF7] shadow-sm'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFile(e.target.files[0]);
            }
          }}
        />

        <div className="flex flex-col items-center">
          <div className="w-14 h-14 rounded-full bg-[#EFE8DC] flex items-center justify-center text-[#D95F32] mb-4 group-hover:scale-110 transition-transform">
            {isUploading ? (
              <Loader2 className="w-7 h-7 animate-spin" />
            ) : (
              <UploadCloud className="w-7 h-7" />
            )}
          </div>

          <h3 className="text-lg font-semibold text-[#252321] mb-1">
            {isUploading ? 'Uploading & inspecting video...' : 'Drop video here, or click to browse'}
          </h3>
          <p className="text-sm text-[#77716A] max-w-sm">
            Supports MP4, MOV, AVI, WEBM, or MKV. Up to 200 MB.
          </p>

          <div className="mt-4 flex items-center gap-2 text-xs font-mono text-[#77716A] bg-[#F7F3EC] px-3 py-1.5 rounded-full border border-[#DED7CC]">
            <span>Metadata inspection</span>
            <span>•</span>
            <span>Local sandbox</span>
            <span>•</span>
            <span>Zero cloud loss</span>
          </div>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="mt-4 p-3.5 rounded-xl bg-[#FDF2F0] border border-[#F5C2B8] text-[#C24F26] text-sm flex items-start gap-2.5">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Notice</p>
            <p className="text-xs text-[#C24F26]/90 mt-0.5">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Or sample divider */}
      <div className="relative my-6 flex items-center justify-center">
        <div className="border-t border-[#DED7CC] w-full" />
        <span className="bg-[#F7F3EC] px-3 text-xs uppercase font-mono tracking-wider text-[#77716A] absolute">
          or evaluate immediately
        </span>
      </div>

      {/* Sample button */}
      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleSampleClick}
          disabled={isUploading || isLoadingSample}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#FFFFFF] border border-[#DED7CC] hover:border-[#D95F32] text-sm font-medium text-[#252321] hover:text-[#D95F32] shadow-xs hover:shadow-sm transition-all disabled:opacity-50"
        >
          {isLoadingSample ? (
            <Loader2 className="w-4 h-4 animate-spin text-[#D95F32]" />
          ) : (
            <PlayCircle className="w-4 h-4 text-[#D95F32]" />
          )}
          <span>Load Synthetic Benchmark Sample (10s, 300 frames)</span>
        </button>
      </div>
    </div>
  );
};
