import type { ApiErrorBody } from "./types";

/** Error carrying the backend's {error: {code, message, details}} envelope. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field-level messages from request validation (422), if any. */
  get fieldErrors(): { field: string; message: string }[] {
    const fields = this.details.fields;
    return Array.isArray(fields) ? (fields as { field: string; message: string }[]) : [];
  }
}

const TOKEN_KEY = "decerno.token";

/**
 * The sign-in token is kept per browser tab (sessionStorage), not per browser (localStorage).
 * With localStorage every tab shared one token, so signing in as someone else in another tab silently
 * changed who this tab was acting as: the page still showed the old user while requests went out as the new one.
 * Per-tab storage keeps each tab on its own account (e.g. employee, technician and admin side by side),
 * and the token is also dropped when the tab is closed.
 */
let inMemory: string | null = null; // fallback when the browser blocks storage

export const tokenStore = {
  get: (): string | null => {
    try { return sessionStorage.getItem(TOKEN_KEY) ?? inMemory; } catch { return inMemory; }
  },
  set: (token: string) => {
    inMemory = token;
    try { sessionStorage.setItem(TOKEN_KEY, token); } catch { /* kept in memory until reload */ }
  },
  clear: () => {
    inMemory = null;
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* nothing to clear */ }
  },
};

// Tokens saved by older versions were shared by every tab; remove them so they cannot leak into a new tab.
try { localStorage.removeItem("itsm.token"); } catch { /* ignore */ }

let unauthorizedHandler: () => void = () => {};

/** AuthProvider registers what to do when a request comes back 401 (session expired). */
export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler;
}

export type Query = Record<string, string | number | boolean | (string | number)[] | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  const qs = params.toString();
  return `/api${path}${qs ? `?${qs}` : ""}`;
}

async function send(method: string, path: string, options: { body?: unknown; query?: Query } = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the server. Is the backend running?");
  }
  if (!response.ok) {
    if (response.status === 401 && token) {
      tokenStore.clear();
      unauthorizedHandler();
    }
    const error = ((await response.json().catch(() => null)) as ApiErrorBody | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `Request failed (${response.status})`,
      error?.details ?? {},
    );
  }
  return response;
}

export async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query } = {},
): Promise<T> {
  const response = await send(method, path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json().catch(() => null)) as T;
}

/** Fetch a file with the user's token (a plain link cannot send it) and hand it to the browser as a download. */
export async function download(path: string, query: Query | undefined, fallbackName: string): Promise<void> {
  const response = await send("GET", path, { query });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const http = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body: body ?? {} }),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
