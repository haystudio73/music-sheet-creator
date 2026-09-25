export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError'; }
}

export const API_BASE = (() => {
  const envUrl = (import.meta as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL;
  if (!envUrl) return '/api';
  const clean = String(envUrl).replace(/\/+$/, '');
  return clean.endsWith('/api') ? clean : `${clean}/api`;
})();

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (cleanPath.startsWith('/api/')) {
    return `${API_BASE}${cleanPath.slice(4)}`;
  }
  return `${API_BASE}${cleanPath}`;
}

export function getClientSession(): string {
  try {
    let session = localStorage.getItem('studio_client_session');
    if (!session) {
      session = (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem('studio_client_session', session);
    }
    return session;
  } catch {
    return '';
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const session = getClientSession();
  const sessionHeader: Record<string, string> = session ? { 'X-Client-Session': session } : {};
  const customHeaders = (init?.headers instanceof Headers)
    ? Object.fromEntries(init.headers.entries())
    : (Array.isArray(init?.headers) ? Object.fromEntries(init.headers) : (init?.headers as Record<string, string> || {}));
  const headers = init?.body instanceof FormData
    ? { ...sessionHeader, ...customHeaders }
    : { 'Content-Type': 'application/json', ...sessionHeader, ...customHeaders };

  try {
    response = await fetch(getApiUrl(path), {
      credentials: API_BASE.startsWith('http') ? 'omit' : 'same-origin',
      ...init,
      headers
    });
  } catch { throw new ApiError('Không kết nối được máy chủ. Kiểm tra lại kết nối mạng hoặc trạng thái backend.', 0); }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === 'string' ? body.detail : body?.detail ? JSON.stringify(body.detail) : `Yêu cầu thất bại (${response.status}).`;
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Có lỗi xảy ra. Vui lòng thử lại.';
export const isActiveJob = (job?: { status: string } | null) => job?.status === 'queued' || job?.status === 'running';
