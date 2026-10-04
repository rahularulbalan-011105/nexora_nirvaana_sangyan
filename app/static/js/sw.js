/* ---------------------------------------------------------------------------
   NIRVAAN service worker.

   Offline policy, deliberately conservative:

   - Static assets (CSS, JS, icons, fonts): cache-first. They are versioned by
     the CACHE name, so a bump invalidates them.
   - Educational pages the user has opened (/learn, /offline, /help): a
     stale-while-revalidate copy, so saved lessons survive going offline.
   - Everything else, especially anything authenticated or AI-backed: network
     only. A cached dashboard would show stale balances and a cached analysis
     would look like a fresh verdict, so neither is cached.
   - POSTs are never cached or replayed.

   When a navigation fails offline, the user gets the offline page - never a
   stale copy of a page that implies live data.
   ------------------------------------------------------------------------- */

const VERSION = "v1";
const STATIC_CACHE = `nirvaan-static-${VERSION}`;
const PAGE_CACHE = `nirvaan-pages-${VERSION}`;

// Precached so the shell renders even on a cold offline start.
const PRECACHE = [
  "/static/css/nirvaan.css",
  "/static/js/nirvaan.js",
  "/static/img/icon.svg",
  "/static/img/favicon.svg",
  "/static/manifest.webmanifest",
  "/static/offline.html",
];

// Pages whose content is educational and safe to serve from cache.
const CACHEABLE_PAGES = ["/learn", "/offline", "/help"];

// Never cached: authenticated state, AI output, or anything that implies
// freshness the cache cannot honour.
const NEVER_CACHE = [
  "/api/",
  "/login",
  "/logout",
  "/register",
  "/dashboard",
  "/check",
  "/talk",
  "/journey",
  "/family",
  "/privacy",
  "/settings",
  "/admin",
  "/batch",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      // addAll rejects wholesale if any entry 404s, so add individually.
      .then((cache) =>
        Promise.allSettled(PRECACHE.map((url) => cache.add(url)))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== STATIC_CACHE && key !== PAGE_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isStatic(url) {
  return url.pathname.startsWith("/static/");
}

function isCacheablePage(url) {
  if (NEVER_CACHE.some((prefix) => url.pathname.startsWith(prefix))) {
    return false;
  }
  return CACHEABLE_PAGES.some((prefix) => url.pathname.startsWith(prefix));
}

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only GET is ever served from cache; never interfere with form posts.
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // Leave cross-origin requests (Tailwind CDN, Google Fonts) to the browser.
  if (url.origin !== self.location.origin) {
    return;
  }

  // Static assets: cache first.
  if (isStatic(url)) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          })
      )
    );
    return;
  }

  // Educational pages: serve cached copy immediately, refresh in background.
  if (isCacheablePage(url)) {
    event.respondWith(
      caches.match(request).then((hit) => {
        const network = fetch(request)
          .then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(PAGE_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          })
          .catch(() => hit || caches.match("/static/offline.html"));
        return hit || network;
      })
    );
    return;
  }

  // Everything else: network only, with the offline page as the failure state.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/static/offline.html"))
    );
  }
});
