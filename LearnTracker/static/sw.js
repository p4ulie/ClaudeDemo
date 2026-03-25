/**
 * Service Worker for LearnTracker PWA.
 * Implements a network-first caching strategy so the app works offline
 * for static assets while always fetching fresh data from the server when possible.
 */

/* Cache version — bump this when static assets change to invalidate old caches */
const CACHE_NAME = "learntracker-v1";

/* List of static assets to pre-cache during service worker installation */
const PRECACHE_URLS = [
  "/",
  "/static/style.css",
  "/static/timer.js",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
];

/**
 * Install event — pre-cache core static assets so the app shell loads offline.
 */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  /* Activate immediately without waiting for old service worker to stop */
  self.skipWaiting();
});

/**
 * Activate event — clean up old caches from previous versions.
 */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  /* Take control of all open tabs immediately */
  self.clients.claim();
});

/**
 * Fetch event — network-first strategy.
 * Try the network first; if it fails (offline), fall back to the cache.
 * API requests are never cached to ensure data freshness.
 */
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  /* Skip caching for API endpoints — always go to network */
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        /* Clone the response and store it in cache for offline use */
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, clone);
        });
        return response;
      })
      .catch(() => {
        /* Network failed — try serving from cache */
        return caches.match(event.request);
      })
  );
});
