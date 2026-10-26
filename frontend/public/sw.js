/*
 * Service worker «Умный друг» — hand-written, no build plugin.
 *
 * What is cached and why:
 *   - `/offline` (+ the static assets its HTML references) and the app icons are precached on install,
 *     so a navigation without network always has something honest to show.
 *   - `/_next/static/*` is content-hashed and immutable → cache-first.
 *   - `/icons/*` → stale-while-revalidate.
 * What is NEVER cached:
 *   - HTML of real pages (network-first; on failure we answer with `/offline`, never with a stale page),
 *   - RSC payloads, `/api/*`, any other origin (the backend at NEXT_PUBLIC_API_URL), any non-GET request.
 *   Pages and API responses carry a child's data and depend on the session; keeping them in a shared
 *   device cache would leak them after logout or to a sibling using the same phone.
 *
 * Bump VERSION whenever the caching rules or the precache list change: old caches are deleted on activate.
 *
 * Web Push (parents): `push` shows the notification built by the backend (`apps/parents/push.py`),
 * `notificationclick` focuses or opens the app on the notifications screen.
 */
const VERSION = "v2";
const CACHE_PREFIX = "ud-";
const PRECACHE = `${CACHE_PREFIX}precache-${VERSION}`;
const STATIC_CACHE = `${CACHE_PREFIX}static-${VERSION}`;
const CURRENT_CACHES = [PRECACHE, STATIC_CACHE];

const OFFLINE_URL = "/offline";
const PRECACHE_URLS = [
  OFFLINE_URL,
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-512-maskable.png",
  "/icons/apple-touch-icon.png",
];

/** Same-origin `/_next/static/...` URLs referenced by an HTML document (scripts, styles, fonts). */
function staticAssetsOf(html) {
  const urls = new Set();
  const pattern = /\/_next\/static\/[\w\-.~%/]+/g;
  for (const match of html.matchAll(pattern)) urls.add(match[0]);
  return [...urls];
}

async function precache() {
  const cache = await caches.open(PRECACHE);
  // `cache: "reload"` bypasses the HTTP cache so a new SW never precaches a stale offline page.
  await cache.addAll(PRECACHE_URLS.map((url) => new Request(url, { cache: "reload" })));
  // Best effort: the offline page must render styled even if the user never opened it online.
  try {
    const response = await cache.match(OFFLINE_URL);
    if (!response) return;
    const assets = staticAssetsOf(await response.text());
    const staticCache = await caches.open(STATIC_CACHE);
    await Promise.all(assets.map((url) => staticCache.add(url).catch(() => undefined)));
  } catch {
    // Missing static assets only degrade the offline page's styling; install must still succeed.
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && !CURRENT_CACHES.includes(key))
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

function isCacheable(response) {
  return response && response.ok && response.type === "basic";
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (isCacheable(response)) {
    const cache = await caches.open(STATIC_CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}

async function staleWhileRevalidate(event) {
  const { request } = event;
  const cached = await caches.match(request);
  const network = fetch(request).then(async (response) => {
    if (isCacheable(response)) {
      const cache = await caches.open(STATIC_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  });
  if (cached) {
    event.waitUntil(network.catch(() => undefined));
    return cached;
  }
  return network;
}

async function networkFirstNavigation(request) {
  try {
    return await fetch(request);
  } catch {
    const offline = await caches.match(OFFLINE_URL, { cacheName: PRECACHE });
    return offline || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Other origins — including the API backend — are never touched by the worker.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  // Flight (RSC) requests carry page data for client-side navigation: never cache them.
  if (request.headers.get("RSC") || url.searchParams.has("_rsc")) return;

  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (url.pathname.startsWith("/icons/")) {
    event.respondWith(staleWhileRevalidate(event));
  }
});

// ---------------------------------------------------------------------------
// Web Push (parents)
// ---------------------------------------------------------------------------
const DEFAULT_NOTIFICATION_URL = "/parent/notifications";

/** Only same-origin destinations: the payload comes from our backend, but a URL is still data. */
function safeTargetUrl(candidate) {
  try {
    const url = new URL(candidate || DEFAULT_NOTIFICATION_URL, self.location.origin);
    return url.origin === self.location.origin ? url.href : new URL(DEFAULT_NOTIFICATION_URL, self.location.origin).href;
  } catch {
    return new URL(DEFAULT_NOTIFICATION_URL, self.location.origin).href;
  }
}

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : "" };
  }
  const options = {
    body: payload.body || "",
    icon: "/icons/icon-192.png",
    tag: payload.tag || undefined,
    renotify: Boolean(payload.tag),
    data: { url: safeTargetUrl(payload.url), notificationId: payload.notification_id },
  };
  event.waitUntil(self.registration.showNotification(payload.title || "Умный друг", options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = safeTargetUrl(event.notification.data && event.notification.data.url);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (existing) {
        await existing.focus();
        if ("navigate" in existing) await existing.navigate(target).catch(() => undefined);
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});

// The push service rotated the subscription: re-subscribe with the same server key. The worker has no
// session, so the backend learns the new endpoint only when the parent toggles push again.
self.addEventListener("pushsubscriptionchange", (event) => {
  const options = event.oldSubscription && event.oldSubscription.options;
  if (!options || !options.applicationServerKey) return;
  event.waitUntil(
    self.registration.pushManager
      .subscribe({ userVisibleOnly: true, applicationServerKey: options.applicationServerKey })
      .catch(() => undefined),
  );
});
