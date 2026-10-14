// Talking to Django: JSON in and out, CSRF token from its cookie. Errors come back as
// { error: 'code', fields?: { name: 'code' } } (see backend views.py / panel.py).

export interface ApiError {
  error: string;
  fields?: Record<string, string>;
  wait?: number;
  status: number;
}

function csrf(): string {
  return document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ?? '';
}

async function handle<T>(response: Response): Promise<T> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // not JSON: a proxy error page, a timeout
  }
  if (!response.ok) {
    const data = (body ?? {}) as Partial<ApiError>;
    throw { error: data.error ?? (response.status >= 500 ? 'server' : 'unknown'), ...data, status: response.status } as ApiError;
  }
  return body as T;
}

async function send<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { credentials: 'same-origin', ...init });
  } catch {
    throw { error: 'network', status: 0 } as ApiError;
  }
  return handle<T>(response);
}

export function get<T>(url: string): Promise<T> {
  return send<T>(url, { headers: { Accept: 'application/json' } });
}

export function post<T>(url: string, body: unknown = {}): Promise<T> {
  return send<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), Accept: 'application/json' },
    body: JSON.stringify(body),
  });
}

export function postForm<T>(url: string, form: FormData): Promise<T> {
  return send<T>(url, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: form });
}

export function islandData<T>(): T {
  const node = document.getElementById('island-data');
  return JSON.parse(node?.textContent || '{}') as T;
}

export function isApiError(value: unknown): value is ApiError {
  return typeof value === 'object' && value !== null && 'error' in value;
}
