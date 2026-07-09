const API_BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

/** Бэкенд отдаёт media-пути относительными ("/media/..."); достраиваем до полного URL. */
export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith('/') ? `${API_BASE_URL}${path}` : path;
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// Access-токен живёт 15 минут; чтобы авторизованные запросы не падали с
// "Недействительный токен" после его истечения, при 401 один раз пытаемся
// обновить токен через refresh-cookie и повторяем запрос. Обновлятель
// регистрирует приложение (см. App.tsx), дедупим параллельные обновления.
let tokenRefresher: (() => Promise<string | null>) | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export function setTokenRefresher(fn: (() => Promise<string | null>) | null): void {
  tokenRefresher = fn;
}

async function refreshAccessToken(): Promise<string | null> {
  if (!tokenRefresher) return null;
  if (!refreshInFlight) {
    refreshInFlight = tokenRefresher().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  skipAuth?: boolean;
}

function rawFetch(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (!options.skipAuth && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

/** Обёртка над fetch: базовый URL, JSON, Authorization, авто-refresh при 401. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await rawFetch(path, options);

  if (res.status === 401 && !options.skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) res = await rawFetch(path, options);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      (data as { code?: string }).code ?? 'unknown_error',
      (data as { message?: string }).message ?? res.statusText,
    );
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Для скачиваемых файлов (напр. экспорт истории) — ответ не JSON, а attachment. */
export async function apiFetchBlob(path: string): Promise<{ blob: Blob; filename: string | null }> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE_URL}${path}`, { headers, credentials: 'include' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      (data as { code?: string }).code ?? 'unknown_error',
      (data as { message?: string }).message ?? res.statusText,
    );
  }

  const disposition = res.headers.get('content-disposition');
  const match = disposition?.match(/filename="([^"]+)"/);
  return { blob: await res.blob(), filename: match?.[1] ?? null };
}

/** Скачивает Blob как файл через временный <a download>. */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
