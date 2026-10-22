import type { ApiErrorPayload, AuthResponse } from "./types";
import { emitAuthLost, getAccessToken, setAccessToken } from "./token";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: ApiErrorPayload["error"]["details"];
  readonly retryAfter?: number;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: ApiErrorPayload["error"]["details"],
    retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = retryAfter;
  }

  static fromResponse(status: number, payload: unknown): ApiError {
    const error = (payload as ApiErrorPayload | null)?.error;
    if (error) {
      return new ApiError(status, error.code, error.message, error.details, error.retry_after);
    }
    return new ApiError(status, status === 0 ? "network" : "error", defaultMessage(status));
  }

  /**
   * Field → first message, for mapping onto form errors. Nested serializer errors such as
   * `{"consents": {"non_field_errors": ["…"]}}` collapse onto the parent key.
   */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    const walk = (value: unknown, path: string) => {
      if (Array.isArray(value)) {
        if (value.length > 0 && path) out[path] = String(value[0]);
        return;
      }
      if (value && typeof value === "object") {
        for (const [key, inner] of Object.entries(value as Record<string, unknown>)) {
          const next = !path ? key : key === "non_field_errors" ? path : `${path}.${key}`;
          walk(inner, next);
        }
        return;
      }
      if (typeof value === "string" && path) out[path] = value;
    };
    if (this.details && typeof this.details === "object") walk(this.details, "");
    return out;
  }
}

function defaultMessage(status: number): string {
  if (status === 0) return "Нет соединения с сервером.";
  if (status >= 500) return "Сервер временно недоступен.";
  return "Ошибка запроса.";
}

async function safeJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  formData?: FormData;
  auth?: boolean;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export type RefreshOutcome =
  | { status: "ok"; session: AuthResponse }
  | { status: "unauthenticated" }
  | { status: "error"; error: ApiError };

let refreshInFlight: Promise<RefreshOutcome> | null = null;

/** Serialises refreshes across browser tabs so a rotated cookie is never reused by a loser tab. */
function withCrossTabLock<T>(fn: () => Promise<T>): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks?.request) {
    return navigator.locks.request("ud-refresh", () => fn()) as Promise<T>;
  }
  return fn();
}

/**
 * Silent refresh via the HttpOnly cookie. Single-flight inside a tab, locked across tabs.
 * Only a 401/403 means the session is gone; network or server errors are reported as such and
 * must not log the user out.
 */
export function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = withCrossTabLock(async (): Promise<RefreshOutcome> => {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/token/refresh/`, {
          method: "POST",
          credentials: "include",
          headers: { Accept: "application/json" },
        });
        if (res.status === 401 || res.status === 403) {
          setAccessToken(null);
          return { status: "unauthenticated" };
        }
        if (!res.ok) {
          return { status: "error", error: ApiError.fromResponse(res.status, await safeJson(res)) };
        }
        const session = (await res.json()) as AuthResponse;
        setAccessToken(session.access);
        return { status: "ok", session };
      } catch {
        return { status: "error", error: new ApiError(0, "network", defaultMessage(0)) };
      }
    }).finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function rawFetch(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (options.body !== undefined && !options.formData) headers["Content-Type"] = "application/json";
  if (token && options.auth !== false) headers.Authorization = `Bearer ${token}`;
  return fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
    credentials: "include",
    signal: options.signal,
  });
}

/**
 * Low-level authenticated fetch for streams and binary responses. Retries once after a silent
 * refresh on 401, exactly like ``api()``, but hands back the raw Response.
 */
export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const build = (token: string | null): RequestInit => ({
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.headers as Record<string, string> | undefined),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  let response = await fetch(`${API_URL}${path}`, build(getAccessToken()));
  if (response.status === 401) {
    const outcome = await refreshSession();
    if (outcome.status === "unauthenticated") {
      emitAuthLost();
      throw new ApiError(401, "not_authenticated", "Нужно войти снова.");
    }
    if (outcome.status === "error") throw outcome.error;
    response = await fetch(`${API_URL}${path}`, build(outcome.session.access));
  }
  return response;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await rawFetch(path, options, getAccessToken());
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, "network", defaultMessage(0));
  }

  const isAuthRoute = path.startsWith("/api/v1/auth/");
  if (response.status === 401 && options.auth !== false && !isAuthRoute) {
    const outcome = await refreshSession();
    if (outcome.status === "unauthenticated") {
      emitAuthLost();
      throw new ApiError(401, "not_authenticated", "Нужно войти снова.");
    }
    if (outcome.status === "error") throw outcome.error;
    try {
      response = await rawFetch(path, options, outcome.session.access);
    } catch {
      throw new ApiError(0, "network", defaultMessage(0));
    }
  }

  if (response.status === 204) return undefined as T;
  const payload = await safeJson(response);
  if (!response.ok) throw ApiError.fromResponse(response.status, payload);
  return payload as T;
}

export function getErrorMessage(error: unknown, fallback = "Что-то пошло не так."): string {
  if (error instanceof ApiError) return error.message || fallback;
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}
