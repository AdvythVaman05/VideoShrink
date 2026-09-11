import type {
  UploadResponse,
  ProcessRequest,
  ProcessResponse,
  CancelResponse,
  JobStatusResponse,
  ProcessResultsResponse,
  ExperimentListResponse,
} from '../types/api';

const API_BASE = '/api';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const data = await res.json();
      if (data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore
    }
    throw new ApiError(res.status, errorDetail);
  }
  return res.json();
}

export const api = {
  async uploadVideo(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<UploadResponse>(res);
  },

  async loadSampleVideo(): Promise<UploadResponse> {
    const res = await fetch(`${API_BASE}/sample/load`, {
      method: 'POST',
    });
    return handleResponse<UploadResponse>(res);
  },

  async startProcessing(payload: ProcessRequest): Promise<ProcessResponse> {
    const res = await fetch(`${API_BASE}/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    return handleResponse<ProcessResponse>(res);
  },

  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    const res = await fetch(`${API_BASE}/process/${jobId}/status`);
    return handleResponse<JobStatusResponse>(res);
  },

  async cancelJob(jobId: string): Promise<CancelResponse> {
    const res = await fetch(`${API_BASE}/process/${jobId}/cancel`, {
      method: 'POST',
    });
    return handleResponse<CancelResponse>(res);
  },

  async getJobResults(jobId: string): Promise<ProcessResultsResponse> {
    const res = await fetch(`${API_BASE}/process/${jobId}/results`);
    return handleResponse<ProcessResultsResponse>(res);
  },

  getDownloadUrl(jobId: string): string {
    return `${API_BASE}/video/${jobId}/download`;
  },

  getStreamUrl(identifier: string, original = false): string {
    return `${API_BASE}/video/${identifier}/stream?original=${original}`;
  },

  async getExperiments(): Promise<ExperimentListResponse> {
    const res = await fetch(`${API_BASE}/experiments`);
    return handleResponse<ExperimentListResponse>(res);
  },

  getExperimentExportUrl(id: string): string {
    return `${API_BASE}/experiments/${id}/export`;
  },
};
