/**
 * Access token lives only in memory (never localStorage); the refresh token is an HttpOnly
 * cookie managed by the backend. A page reload therefore starts with a silent refresh.
 */

let accessToken: string | null = null;
const authLostListeners = new Set<() => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function onAuthLost(listener: () => void): () => void {
  authLostListeners.add(listener);
  return () => authLostListeners.delete(listener);
}

export function emitAuthLost(): void {
  accessToken = null;
  authLostListeners.forEach((listener) => listener());
}
