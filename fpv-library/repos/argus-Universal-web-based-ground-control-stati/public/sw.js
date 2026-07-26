const CACHE_NAME = 'argus-gcs-v3.6';
const TILE_CACHE = 'argus-tiles-v1';
const MAX_TILE_ENTRIES = 5000;

const APP_SHELL = [
  '/',
  '/manifest.json',
  '/images/icon-192.png',
  '/images/icon-512.png',
  '/lib/leaflet/leaflet.css',
  '/lib/leaflet/leaflet.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== TILE_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  if (url.pathname.startsWith('/ws') ||
      (url.pathname.startsWith('/api/') && !url.pathname.startsWith('/api/tile/'))) {
    return;
  }

  if (url.pathname.startsWith('/api/tile/')) {
    e.respondWith(handleTileRequest(e.request));
    return;
  }

  if (url.pathname.startsWith('/assets/')) {
    e.respondWith(cacheFirst(e.request, CACHE_NAME));
    return;
  }

  e.respondWith(staleWhileRevalidate(e.request, CACHE_NAME));
});

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, resp.clone());
    }
    return resp;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cached = await caches.match(request);
  const fetchPromise = fetch(request)
    .then((resp) => {
      if (resp.ok) {
        caches.open(cacheName).then((c) => c.put(request, resp.clone()));
      }
      return resp;
    })
    .catch(() => cached || new Response('Offline', { status: 503 }));
  return cached || fetchPromise;
}

async function handleTileRequest(request) {
  const cache = await caches.open(TILE_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      await cache.put(request, resp.clone());
      evictOldTiles(cache);
    }
    return resp;
  } catch {
    return new Response('', { status: 404 });
  }
}

async function evictOldTiles(cache) {
  const keys = await cache.keys();
  if (keys.length > MAX_TILE_ENTRIES) {
    const toDelete = keys.slice(0, keys.length - MAX_TILE_ENTRIES);
    await Promise.all(toDelete.map((k) => cache.delete(k)));
  }
}

self.addEventListener('message', (e) => {
  if (e.data === 'skipWaiting') {
    self.skipWaiting();
  }

  if (e.data && e.data.type === 'PRECACHE_ASSETS') {
    e.waitUntil(precacheAssets(e.data.urls));
  }

  if (e.data && e.data.type === 'CACHE_TILES') {
    e.waitUntil(prefetchTiles(e.data.urls));
  }

  if (e.data && e.data.type === 'CLEAR_TILE_CACHE') {
    e.waitUntil(caches.delete(TILE_CACHE));
  }

  if (e.data && e.data.type === 'GET_CACHE_STATS') {
    getCacheStats().then((stats) => {
      e.source.postMessage({ type: 'CACHE_STATS', ...stats });
    });
  }
});

async function precacheAssets(urls) {
  const cache = await caches.open(CACHE_NAME);
  for (const url of urls) {
    try {
      const existing = await cache.match(url);
      if (!existing) {
        const resp = await fetch(url, { credentials: 'same-origin' });
        if (resp.ok) await cache.put(url, resp);
      }
    } catch {
      // skip unreachable assets
    }
  }
}

async function prefetchTiles(urls) {
  const cache = await caches.open(TILE_CACHE);
  for (const url of urls) {
    try {
      const existing = await cache.match(url);
      if (!existing) {
        const resp = await fetch(url);
        if (resp.ok) await cache.put(url, resp);
      }
    } catch {
      // skip failed tiles
    }
  }
}

async function getCacheStats() {
  const appCache = await caches.open(CACHE_NAME);
  const tileCache = await caches.open(TILE_CACHE);
  const appKeys = await appCache.keys();
  const tileKeys = await tileCache.keys();
  return {
    appEntries: appKeys.length,
    tileEntries: tileKeys.length,
    maxTiles: MAX_TILE_ENTRIES,
  };
}

self.addEventListener('push', (e) => {
  if (!e.data) return;
  try {
    const data = e.data.json();
    e.waitUntil(
      self.registration.showNotification(data.title || 'Argus GCS', {
        body: data.body || '',
        icon: '/images/icon-192.png',
        badge: '/images/icon-192.png',
        tag: data.tag || 'argus-alert',
        data: { url: data.url || '/' },
      })
    );
  } catch {
    // ignore malformed push
  }
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
