/**
 * Browser side of Web Push: capability detection and the PushManager calls.
 * Talking to the backend lives in `features/parent/push.ts`; this module knows nothing about the API.
 */

import { isIosSafari, isStandalone } from "@/lib/pwa";

export type PushSupport = "unsupported" | "needs-install" | "denied" | "ready";

/** Why push may be unavailable on this device, decided before touching the service worker. */
export function detectPushSupport(): PushSupport {
  if (typeof window === "undefined") return "unsupported";
  const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (!supported) {
    // iOS Safari exposes PushManager only to apps installed on the home screen (16.4+).
    return isIosSafari() && !isStandalone() ? "needs-install" : "unsupported";
  }
  return Notification.permission === "denied" ? "denied" : "ready";
}

/** VAPID public key (base64url X9.62 point, as served by the API) → bytes for `applicationServerKey`. */
export function urlBase64ToUint8Array(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url + "=".repeat((4 - (base64url.length % 4)) % 4);
  const binary = window.atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

/**
 * The app's service worker registration, or `null` when there is none (dev builds, unsupported browsers).
 * `navigator.serviceWorker.ready` never settles without a registration, so it is awaited only once one exists.
 */
export async function getPushRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  const registration = await navigator.serviceWorker.getRegistration("/");
  if (!registration) return null;
  return registration.active ? registration : navigator.serviceWorker.ready;
}

export async function getPushSubscription(): Promise<PushSubscription | null> {
  const registration = await getPushRegistration();
  return registration ? registration.pushManager.getSubscription() : null;
}

function sameKey(subscription: PushSubscription, key: Uint8Array): boolean {
  const current = subscription.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === key.length && bytes.every((byte, index) => byte === key[index]);
}

/** Whether the browser subscription was made for this server key; after a key rotation it must be redone. */
export function hasServerKey(subscription: PushSubscription, publicKey: string): boolean {
  return sameKey(subscription, urlBase64ToUint8Array(publicKey));
}

/** SHA-256 hex digest. The API receives this instead of the endpoint, which is a capability URL. */
export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export class NoServiceWorkerError extends Error {
  constructor() {
    super("Service worker is not registered");
    this.name = "NoServiceWorkerError";
  }
}

/** Subscribe this browser; a subscription made with another (rotated) server key is replaced. */
export async function subscribeBrowser(publicKey: string): Promise<PushSubscription> {
  const registration = await getPushRegistration();
  if (!registration) throw new NoServiceWorkerError();
  const key = urlBase64ToUint8Array(publicKey);
  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    if (sameKey(existing, key)) return existing;
    await existing.unsubscribe();
  }
  return registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
}
