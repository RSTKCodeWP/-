// Service worker for offline support. Registered from every page (see
// assets/site-header.js) with the default scope of "/" (this file's
// directory), so it covers the hub and every tool.
//
// Bump CACHE_NAME whenever the precache list below changes so clients
// pick up the new set instead of serving a stale mix.
const CACHE_PREFIX = "fpv-tools-";
const CACHE_NAME = `${CACHE_PREFIX}v2`;

// Cross-origin hosts we deliberately cache for offline use (e.g. the IGOW
// tool loads sql.js from here). Anything else cross-origin is passed
// straight through to the network, uncached.
const TRUSTED_CROSS_ORIGIN_HOSTS = new Set(["cdnjs.cloudflare.com"]);

// App shell: kept as an explicit list (no build step to auto-discover
// files). Add new tool pages/assets here when they're created.
const PRECACHE_URLS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./assets/site-header.js",
  "./assets/site-header.css",
  "./assets/icons/icon-32.png",
  "./assets/icons/icon-192.png",
  "./assets/icons/icon-512.png",
  "./assets/icons/icon-512-maskable.png",
  "./assets/icons/apple-touch-icon.png",
  "./cli-merge/",
  "./cli-merge/index.html",
  "./cli-merge/src/parser.js",
  "./cli-merge/src/output.js",
  "./cli-merge/src/validator.js",
  "./rate-profile/",
  "./rate-profile/index.html",
  "./rate-profile/styles.css",
  "./rate-profile/src/app.js",
  "./rate-profile/src/profile-manager.js",
  "./rate-profile/src/graph-renderer.js",
  "./rate-profile/src/cli-parser.js",
  "./rate-profile/src/rate-calculator.js",
  "./igow/",
  "./igow/index.html",
  "./igow/igow.db",
  "./prop-motor-sizer/",
  "./prop-motor-sizer/index.html",
  "./prop-motor-sizer/styles.css",
  "./prop-motor-sizer/src/app.js",
  "./prop-motor-sizer/src/sizer-calculator.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        )
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  const isSameOrigin = url.origin === self.location.origin;
  if (!isSameOrigin && !TRUSTED_CROSS_ORIGIN_HOSTS.has(url.hostname)) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request);
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok || response.type === "opaque") {
            cache.put(event.request, response.clone());
          }
          return response;
        })
        .catch(() => undefined);

      // Stale-while-revalidate: serve cache immediately and refresh in the
      // background (kept alive via waitUntil); if nothing is cached yet,
      // wait for the network instead.
      event.waitUntil(network);
      return cached ?? (await network) ?? Response.error();
    }),
  );
});
