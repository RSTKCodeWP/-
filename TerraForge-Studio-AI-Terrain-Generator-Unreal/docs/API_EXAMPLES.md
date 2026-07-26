# API Examples

Working examples for the TerraForge Studio HTTP API.

Every request and response below was captured against a running instance. The
authoritative schema is always the live one at `http://localhost:8000/docs`
(Swagger UI) or `http://localhost:8000/openapi.json`.

Base URL in these examples: `http://localhost:8000`

## Table of Contents

- [Health and readiness](#health-and-readiness)
- [Discovery](#discovery)
- [Terrain generation](#terrain-generation)
- [Task management](#task-management)
- [Downloads](#downloads)
- [Batch processing](#batch-processing)
- [Vector data (roads and buildings)](#vector-data-roads-and-buildings)
- [Testing a data source](#testing-a-data-source)
- [Webhooks](#webhooks)
- [Authentication and users](#authentication-and-users)
- [Rate limiting](#rate-limiting)

---

## Health and readiness

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "environment": "development",
  "data_sources": {
    "available": ["srtm"],
    "configured": ["srtm", "osm"],
    "total": 2
  },
  "settings": {
    "max_area_km2": 100.0,
    "default_resolution": 2048,
    "synthetic_fallback": true
  }
}
```

Orchestrator probes live at the root, matching `k8s/deployment.yml`:

```bash
curl http://localhost:8000/health/live     # process is up
curl http://localhost:8000/health/ready    # storage writable + a source usable
curl http://localhost:8000/metrics         # Prometheus scrape target
```

`/health/ready` returns **503** when the output directory is not writable or no
elevation source is reachable, so traffic is kept away until the instance can
actually serve a generation.

---

## Discovery

### Elevation and vector sources

```bash
curl http://localhost:8000/api/sources
```

`srtm` is the key-free default; the rest activate once credentials are set
in `.env`.

### Export formats

```bash
curl http://localhost:8000/api/formats
```

Reports valid resolutions per engine, for example `[1009, 2017, 4033, 8129]`
for Unreal Engine 5 landscapes.

---

## Terrain generation

### Minimal request

Only `name` and `bbox` are required.

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "san_francisco",
    "bbox": {"north": 37.81, "south": 37.75, "east": -122.39, "west": -122.48}
  }'
```

### Full request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "san_francisco",
    "bbox": {"north": 37.81, "south": 37.75, "east": -122.39, "west": -122.48},
    "resolution": 1009,
    "export_formats": ["unreal5", "unity", "gltf", "geotiff"],
    "elevation_source": "auto",
    "enable_roads": false,
    "enable_buildings": false,
    "enable_weightmaps": true
  }'
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | Becomes the output directory name; letters, digits, space, `.`, `_`, `-`, max 64 chars |
| `bbox` | object | required | `north > south`, `east > west`, WGS84 degrees |
| `resolution` | int | `2048` | 64–8192; UE5 snaps to the nearest valid landscape size |
| `export_formats` | array | `["unreal5"]` | `unreal5`, `unity`, `gltf`, `geotiff`, or `all` |
| `elevation_source` | string | `"auto"` | `auto`, `srtm`, `opentopography`, `azure_maps`, `sentinelhub` |
| `enable_weightmaps` | bool | `true` | Material layers for UE5/Unity |
| `enable_roads` / `enable_buildings` | bool | `true` | Fetched from OpenStreetMap; see [Vector data](#vector-data-roads-and-buildings) |

Responds **202 Accepted** with a queued task:

```json
{
  "task_id": "6ca21032-c327-4dd0-a97a-6d5b7ea86ca6",
  "status": "pending",
  "progress": 0.0,
  "current_step": "Queued for processing",
  "warnings": [],
  "result": null
}
```

### Validation errors

| Condition | Status |
|---|---|
| `north <= south`, `east <= west`, coordinates out of range | 422 |
| `resolution` outside 64–8192 | 422 |
| `name` containing a path separator, empty, or over 64 chars | 422 |
| Area larger than `MAX_AREA_KM2` | 400 |

---

## Task management

### Poll a task

```bash
curl http://localhost:8000/api/status/6ca21032-c327-4dd0-a97a-6d5b7ea86ca6
```

A completed generation:

```json
{
  "task_id": "6ca21032-c327-4dd0-a97a-6d5b7ea86ca6",
  "status": "completed",
  "progress": 100.0,
  "current_step": "Complete",
  "warnings": [],
  "download_url": "/api/maps/san_francisco/download/zip",
  "result": {
    "terrain_name": "san_francisco",
    "resolution": 1009,
    "area_km2": 52.5351,
    "elevation": {
      "source": "srtm",
      "synthetic": false,
      "min_elevation_m": -25.17,
      "max_elevation_m": 280.61
    },
    "exports": [
      {"format": "unreal5", "success": true, "directory": "output/san_francisco/unreal5", "files": {"heightmap": "...", "metadata": "..."}},
      {"format": "geotiff", "success": false, "error": "rasterio is required for GeoTIFF export"}
    ],
    "output_directory": "output/san_francisco",
    "duration_seconds": 2.7,
    "cached": false
  }
}
```

Two fields deserve attention:

- **`result.elevation`** names the source that actually supplied the heightmap.
  When `synthetic` is `true` the terrain is procedural, not measured, and a
  matching entry appears in `warnings`. Check this before treating output as
  real-world data.
- **`exports`** reports each format independently. A format can fail (usually a
  missing optional dependency) while others succeed; the task only fails when
  *every* format fails.

When roads or buildings are requested and retrieved, the result also carries a
`vectors` block:

```json
"vectors": {
  "source": "overpass",
  "roads": 128,
  "buildings": 342,
  "landuse": 0,
  "path": "output/san_francisco/vectors.geojson"
}
```

The features are written to `vectors.geojson` in the output directory (and
therefore included in the zip download) as a GeoJSON FeatureCollection: roads
as `LineString`, buildings and land use as closed `Polygon`. Each feature keeps
its OSM attributes - lanes, maxspeed, surface, oneway for roads; building type
and levels for buildings.

### Repeated requests

An identical request — same name, area, resolution, formats and feature flags —
is served from the result cache instead of being regenerated. The response is
the same shape, with `cached: true` and the artifacts restored to the output
directory:

```json
"result": { "cached": true, "duration_seconds": 0.0 }
```

The cache is controlled by `ENABLE_CACHE`, `CACHE_EXPIRY_DAYS` and
`CACHE_MAX_SIZE_GB`, and inspected through `/api/cache/stats` and
`/api/cache/entries`. Entries are evicted by least-recent use when the size
limit is reached. A damaged entry falls back to regenerating rather than
serving broken output.

The terrain name is part of the cache key because exported files are named
after it; two names therefore never share an entry.

### List tasks

```bash
curl http://localhost:8000/api/tasks
```

```json
{ "count": 2, "tasks": [ { "task_id": "...", "status": "completed" } ] }
```

### Live updates over WebSocket

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/generation/${taskId}`);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'status_update') {
    console.log(msg.progress, msg.current_step, msg.warnings);
  }
};
```

`status_update` carries the full task payload, identical to
`GET /api/status/{task_id}` plus a `type` field.

---

## Downloads

### Whole map as a zip

```bash
curl -O -J http://localhost:8000/api/maps/san_francisco/download/zip
```

The archive is cached and only rebuilt when the map directory changes.

### Individual files

```bash
curl -O http://localhost:8000/api/maps/san_francisco/download/heightmap   # UE5 16-bit PNG
curl -O http://localhost:8000/api/maps/san_francisco/download/metadata    # import settings
curl -O http://localhost:8000/api/maps/san_francisco/download/thumbnail   # preview PNG
```

Any other `file_type` returns 400; an unknown map returns 404.

### List generated maps

```bash
curl http://localhost:8000/api/maps
```

```json
{
  "count": 1,
  "maps": [
    {
      "name": "san_francisco",
      "path": "output/san_francisco",
      "has_thumbnail": true,
      "formats": ["geotiff", "gltf", "unity", "unreal5"]
    }
  ]
}
```

---

## Batch processing

Queue several generations at once:

```bash
curl -X POST http://localhost:8000/api/batch/add \
  -H "Content-Type: application/json" \
  -d '{
    "jobs": [
      {"name": "area_one", "bbox": {"north": 37.81, "south": 37.79, "east": -122.39, "west": -122.41}},
      {"name": "area_two", "bbox": {"north": 40.76, "south": 40.75, "east": -73.98, "west": -73.99}}
    ],
    "priority": 0
  }'
```

```bash
curl http://localhost:8000/api/batch/jobs            # all jobs
curl http://localhost:8000/api/batch/stats           # queue statistics
curl -X POST http://localhost:8000/api/batch/jobs/{job_id}/retry
```

Batch jobs run on the same generator as `/api/generate`, so they also appear
under `/api/tasks`.

---

## Webhooks

Subscribe to generation events instead of polling.

```bash
curl -X POST http://localhost:8000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/terraforge-hook",
    "events": ["generation.completed", "generation.failed"],
    "secret": "a-sufficiently-long-secret"
  }'
```

Available events come from `GET /api/webhooks/events`:
`generation.started`, `generation.completed`, `generation.failed`.

The `secret` is write-only. Responses report `has_secret` and never echo the
value back.

### Verifying a delivery

Each POST carries `X-TerraForge-Signature: sha256=<hex>`, an HMAC-SHA256 over
the **exact request body bytes**:

```python
import hashlib
import hmac

def verify(request_body: bytes, header: str, secret: str) -> bool:
    algorithm, _, digest = header.partition("=")
    if algorithm != "sha256":
        return False
    expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)
```

Verify against the raw body, not a re-serialized copy: any difference in key
order or whitespace changes the digest.

Failed deliveries are retried up to three times with exponential backoff.
A 4xx response is treated as a permanent rejection and is not retried. A
subscriber that is down never affects the generation that triggered the event.

---

## Vector data (roads and buildings)

Roads and buildings come from OpenStreetMap. Two paths exist:

| Source | Requirements | Notes |
|---|---|---|
| **Overpass** (default) | none beyond `httpx` | Plain HTTP against public Overpass mirrors |
| osmnx | `pip install -r requirements-optional.txt` | Richer attributes, pulls in geopandas/GDAL |

Overpass is queried first when osmnx is not installed, so vector data works on
a default install. Configure it in `.env`:

```bash
OVERPASS_ENABLED=true
OVERPASS_ENDPOINTS=https://overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter
OVERPASS_TIMEOUT=90
OVERPASS_MAX_AREA_KM2=25.0
```

Requests fall back across the configured mirrors and retry on 429/502/503/504,
since Overpass instances rate-limit independently. Areas larger than
`OVERPASS_MAX_AREA_KM2` are skipped rather than submitted - Overpass is a
shared public service and large queries are expensive for it. When that
happens, or when every mirror fails, the task completes with a warning and no
`vectors` block rather than failing.

Footpaths, cycleways, steps and private-access ways are excluded from road
extraction.

---

## Testing a data source

```bash
curl -X POST http://localhost:8000/api/settings/test-connection/srtm
```

```json
{
  "source": "srtm",
  "success": true,
  "configured": true,
  "reachable": true,
  "message": "Connection successful",
  "error": null
}
```

The probe performs a real request against the provider — a terrain tile for
`srtm`, a trivial query for `osm`, a token exchange for `sentinelhub`, an
authenticated call for `opentopography` and `azure_maps`. Three fields matter,
and they are deliberately distinct:

| Field | Meaning |
|---|---|
| `configured` | Credentials are present (always true for key-free sources) |
| `reachable` | The request completed and was accepted; `null` when none was attempted |
| `success` | `reachable === true` — nothing else counts |

A rejected key returns `success: false` with an explicit reason rather than a
green result. A disabled or unconfigured source reports `reachable: null`,
which is neither a pass nor a failure and should not be shown as an error.

---

## Authentication and users

Accounts are optional: terrain generation, downloads and vector queries all
work unauthenticated. Authentication exists for multi-user deployments, where
it separates rate-limit budgets and gates the administrative endpoints.

### Register

```bash
read -rs TERRAFORGE_PASSWORD          # keep the password out of your shell history

curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg p "$TERRAFORGE_PASSWORD" \
        '{username: "alice", email: "alice@example.com", password: $p}')"
```

```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "user_id": "jj62qGXqQtuWUa_EIwZkOA",
    "username": "alice",
    "email": "alice@example.com",
    "role": "user",
    "created_at": "2026-07-26T22:48:23.503329",
    "last_login": null,
    "is_active": true
  }
}
```

New accounts always get the `user` role. `admin` is never self-assignable —
see [Roles](#roles) below.

### Log in

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg p "$TERRAFORGE_PASSWORD" \
        '{username: "alice", password: $p}')"
```

```json
{
  "success": true,
  "message": "Login successful",
  "session": {
    "token": "JSgCtxNuFa5yTJI282opENQ8CiDEVtSNrhzyA45bjWs",
    "expires_at": "2026-07-27T22:48:23.652318"
  },
  "user": { "user_id": "jj62qGXqQtuWUa_EIwZkOA", "role": "user", "...": "..." }
}
```

Sessions last 24 hours and are refreshed on each authenticated request. A bad
password returns **401** `{"detail": "Invalid username or password"}` — the
same response as an unknown username, so the endpoint does not reveal which
accounts exist.

### Authenticated requests

Pass the session token as a bearer token:

```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer JSgCtxNuFa5yTJI282opENQ8CiDEVtSNrhzyA45bjWs"
```

```json
{
  "user": {
    "user_id": "jj62qGXqQtuWUa_EIwZkOA",
    "username": "alice",
    "email": "alice@example.com",
    "role": "user",
    "created_at": "2026-07-26T22:48:23.503329",
    "last_login": "2026-07-26T22:48:23.652351",
    "is_active": true
  }
}
```

Without a valid token the endpoint returns **401** `{"detail": "Not
authenticated"}`. User payloads never include the password hash.

### Log out

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

```json
{ "success": true, "message": "Logged out successfully" }
```

The token is invalidated immediately; reusing it returns **401**.

### Updating an account

A user may update their own record; admins may update anyone's:

```bash
curl -X PATCH http://localhost:8000/api/auth/users/$USER_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice.new@example.com"}'
```

```json
{ "success": true, "message": "User updated successfully" }
```

Only `email`, `role` and `is_active` are writable. `username`, `user_id`,
`created_at` and the password hash are ignored if sent.

### Roles

| Role | Can |
|------|-----|
| `user` | manage own account |
| `admin` | additionally list, update and delete any user, change roles, clean up sessions |

`role` is an administrative field. A non-admin sending it gets **403**, whether
or not the target is their own account:

```bash
curl -X PATCH http://localhost:8000/api/auth/users/$USER_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin"}'
```

```json
{ "detail": "Only an admin can change roles" }
```

Admin-only endpoints return **403** `{"detail": "Admin access required"}`:

```
GET    /api/auth/users
DELETE /api/auth/users/{user_id}
POST   /api/auth/sessions/cleanup
```

The first admin has to be promoted out of band — start a Python shell against
the same storage file:

```python
from realworldmapgen.core.auth_manager import get_auth_manager

auth = get_auth_manager()
user = next(u for u in auth.list_users() if u.username == "alice")
auth.update_user(user.user_id, {"role": "admin"})
```

`set_password(user_id, password)` on the same object is the reset path for a
forgotten password.

### Storage and password hashing

Accounts live in a JSON file, outside the cache directory so that clearing the
cache never destroys credentials:

```bash
AUTH_STORAGE_FILE=data/users.json
```

Passwords are stored as PBKDF2-HMAC-SHA256 with a random 16-byte per-user salt
and 260,000 iterations, in the format
`pbkdf2_sha256$<iterations>$<salt-hex>$<digest-hex>`:

```json
{
  "users": {
    "jj62qGXqQtuWUa_EIwZkOA": {
      "username": "alice",
      "role": "user",
      "password_hash": "pbkdf2_sha256$260000$ea3cea93d6f4cd43...$db70818694177de2..."
    }
  }
}
```

Accounts created by earlier builds carry a bare SHA-256 digest. They still
authenticate, and are transparently rehashed to PBKDF2 on the next successful
login — no reset is required. Because those digests were unsalted, treat any
password used before the upgrade as exposed if the file was ever readable by
someone else.

---

## Rate limiting

Enabled by default and configurable in `.env`:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000
```

Every response carries the current budget:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 57
```

Exceeding a budget returns **429** with a standards-compliant `Retry-After`:

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 60 per minute",
  "retry_after": 60
}
```

`/health*` and `/metrics` are exempt, so orchestrator probes and Prometheus
scrapes are never throttled.

Clients are identified by authenticated user id when available, otherwise by
socket address. `X-Forwarded-For` is **ignored by default** because any client
can set it; enable `RATE_LIMIT_TRUST_FORWARDED_FOR=true` only when running
behind a proxy that overwrites the header.
