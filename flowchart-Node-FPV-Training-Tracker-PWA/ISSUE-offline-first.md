# Offline-first support: queue writes when server is unreachable

## Problem

The PWA currently uses a network-first strategy for API calls with a cache fallback for GETs. This means:

- **Static assets load fine offline** — HTML/CSS/JS are cache-first
- **Previously-viewed read-only pages show cached data** — tricks, schedule, denver items, stats
- **All write operations fail** — creating sessions, adding packs, logging trick attempts, crashes, reviews

This is a problem because the primary use case is logging sessions *at the field* (park, outdoor spot), where the phone has cellular internet but **cannot reach the Runtipi server on the home LAN**.

The app is essentially read-only reference material when away from home, which defeats the purpose.

## Desired Behavior

The app should work identically whether the server is reachable or not. Data syncs automatically when connectivity to the server is restored.

## Implementation Sketch

1. **IndexedDB local store** — mirror the SQLite schema client-side. All reads and writes go to IndexedDB first so the app is fully functional offline.

2. **Write queue with background sync** — mutations (POST/PUT/DELETE) get queued in IndexedDB and replayed to the server when connectivity returns. Use the [Background Sync API](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API) where supported, with a manual poll fallback.

3. **ID mapping** — local records use temporary IDs (e.g. negative integers or UUIDs). On sync, the server returns real IDs and the client remaps foreign keys (session → packs, session → trick_attempts, etc.).

4. **Conflict resolution** — server is source of truth. On sync: push local changes first (with dedup by date/time_start/location for sessions), then pull latest server state. Last-write-wins for simple fields.

5. **Online/offline indicator** — visible status showing sync state: "synced", "pending changes (3)", "offline".

6. **Sync trigger** — attempt sync on: `navigator.onLine` event, visibility change (app foregrounded), periodic timer (every 30s when online), and manual "sync now" button.

## Scope

- No changes to the server API are needed — the existing REST endpoints and JSON import/export already handle the wire format
- The service worker fetch handler needs updating to route through IndexedDB instead of just caching raw responses
- `app.js` needs an abstraction layer: `api()` → `localDb.write()` + `syncQueue.enqueue()`

## Affected Files

- `public/app.js` — all `api()` calls need to go through local-first layer
- `public/sw.js` — sync registration, possibly intercept API calls differently
- New: `public/db.js` — IndexedDB schema + CRUD operations
- New: `public/sync.js` — queue management, conflict resolution, server communication
