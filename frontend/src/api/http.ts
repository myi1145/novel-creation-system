import type { ApiResponse } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export class ApiError extends Error {
  status?: number;
  code?: string;
  details?: unknown;

  constructor(message: string, options?: { status?: number; code?: string; details?: unknown }) {
    super(message);
    this.name = 'ApiError';
    this.status = options?.status;
    this.code = options?.code;
    this.details = options?.details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    let code: string | undefined;
    let details: unknown;
    try {
      const payload = (await response.json()) as { message?: string; code?: string; details?: unknown };
      if (payload.message) message = payload.message;
      code = payload.code;
      details = payload.details;
    } catch {
      // ignore non-json errors and fallback to HTTP status message
    }
    throw new ApiError(message, { status: response.status, code, details });
  }

  const payload = (await response.json()) as ApiResponse<T>;
  if (!payload.success) {
    throw new ApiError(payload.message || '请求失败');
  }
  return payload.data;
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
};
