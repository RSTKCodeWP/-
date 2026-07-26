# 🌐 TerraForge Studio - REST API Specification

**Base URL**: `http://localhost:8000` (the API is served by the application you
run; there is no hosted service)
**Format**: JSON

This document describes the API as implemented. It is written against the
schema the running application publishes, which stays authoritative:

- **OpenAPI**: `http://localhost:8000/openapi.json`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

Worked request/response examples live in [API_EXAMPLES.md](API_EXAMPLES.md).

---

## 📋 Table of Contents

1. [Conventions](#conventions)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Core models](#core-models)
5. [Error handling](#error-handling)
6. [Rate limiting](#rate-limiting)
7. [Webhooks](#webhooks)

---

## 📐 Conventions

- Requests and responses are JSON, except file downloads and the frontend.
- Timestamps are ISO 8601 strings.
- Bounding boxes are `{"north": …, "south": …, "east": …, "west": …}` in
  WGS84 degrees. GeoJSON coordinates follow the standard `[lon, lat]` order.
- Long-running work returns a `task_id` immediately; poll
  `GET /api/status/{task_id}` or subscribe over WebSocket.

---

## 🔐 Authentication

The API is **unauthenticated by default**. A freshly started instance serves
every endpoint except the administrative ones without credentials, which suits
the desktop and single-user cases the application is built around.

Two independent mechanisms can be turned on.

### 1. User accounts and sessions

Per-user accounts with roles, used for the administrative endpoints and to give
each user their own rate-limit budget.

```http
POST /api/auth/register
POST /api/auth/login      →  {"session": {"token": "…", "expires_at": "…"}}
```

```http
Authorization: Bearer <session-token>
```

Sessions last 24 hours and are refreshed on each authenticated request.
Passwords are stored as salted PBKDF2-HMAC-SHA256. Roles are `user` and
`admin`; only an admin can set the `role` field, including on their own
account. Full flow in
[API_EXAMPLES.md](API_EXAMPLES.md#authentication-and-users).

### 2. Deployment-level API keys

A shared-secret gate in front of the whole API, for instances exposed beyond
localhost:

```bash
API_KEY_ENABLED=true
API_KEYS=key-one,key-two
```

```http
X-API-Key: key-one
```

The key may also be sent as `Authorization: Bearer <key>`. Requests to `/api…`
without a valid key return **401**:

```json
{
  "error": "Unauthorized",
  "message": "A valid API key is required. Send it as X-API-Key."
}
```

`/api/health`, `/health*`, `/metrics`, `/docs`, `/redoc` and `/openapi.json`
stay reachable so orchestrator probes and schema discovery keep working.
Enabling the gate with an empty `API_KEYS` list rejects every API request
rather than failing open.

The two mechanisms compose: send the key in `X-API-Key` and the session token
in `Authorization`.

---

## 📍 Endpoints

### Terrain generation

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start a generation; returns a `task_id` |
| `GET` | `/api/status/{task_id}` | Progress and result for a task |
| `GET` | `/api/tasks` | List tasks |
| `GET` | `/api/tasks/{task_id}` | Alias of `/api/status/{task_id}` |
| `GET` | `/api/sources` | Available elevation and vector sources |
| `GET` | `/api/formats` | Available export formats |
| `GET` | `/api` | API root: version and endpoint index |

### Downloads

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/maps` | Generated maps on disk |
| `GET` | `/api/maps/{map_name}/download/{file_type}` | `heightmap`, `metadata`, `thumbnail`, or `zip` for the whole map |

### Health and metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Overall health |
| `GET` | `/health/live` | Liveness probe: the process is up |
| `GET` | `/health/ready` | Readiness probe: disk writable, a source reachable |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/health` | Health, under the API prefix |

### Batch processing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/batch/add` | Queue one or more jobs |
| `POST` | `/api/batch/process` | Start processing the queue |
| `GET` | `/api/batch/jobs` | List jobs |
| `GET` | `/api/batch/jobs/{job_id}` | Job detail and progress |
| `POST` | `/api/batch/jobs/{job_id}/cancel` | Cancel a job |
| `POST` | `/api/batch/jobs/{job_id}/retry` | Retry a failed job |
| `GET` | `/api/batch/downloads/{job_id}` | Files produced by a job |
| `GET` | `/api/batch/stats` | Queue statistics |
| `POST` | `/api/batch/clear` | Drop completed jobs |

### Authentication and users

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/register` | Create an account (always role `user`) |
| `POST` | `/api/auth/login` | Exchange credentials for a session token |
| `POST` | `/api/auth/logout` | Invalidate the current session |
| `GET` | `/api/auth/me` | The authenticated user |
| `GET` | `/api/auth/users` | List users — **admin** |
| `PATCH` | `/api/auth/users/{user_id}` | Update `email`, `is_active`; `role` is **admin** only |
| `DELETE` | `/api/auth/users/{user_id}` | Delete a user — **admin** |
| `POST` | `/api/auth/sessions/cleanup` | Drop expired sessions — **admin** |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings/` | Current settings |
| `POST` | `/api/settings/` | Update settings |
| `GET` | `/api/settings/masked` | Credentials, masked to their last 4 characters |
| `POST` | `/api/settings/test-connection/{source}` | Probe a data source for real |
| `GET` | `/api/settings/export` | Export settings, credentials optional |
| `POST` | `/api/settings/import` | Import settings |
| `POST` | `/api/settings/reset` | Reset to defaults |
| `GET` | `/api/settings/first-run` | Whether the setup wizard is pending |
| `POST` | `/api/settings/complete-wizard` | Mark the wizard done |

### Cache

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cache/stats` | Size, entry count, hit rate |
| `GET` | `/api/cache/entries` | List entries |
| `GET` | `/api/cache/entry/{cache_key}` | One entry's metadata |
| `DELETE` | `/api/cache/{cache_key}` | Remove one entry |
| `POST` | `/api/cache/optimize` | Evict least-recently-used entries when over the size cap |
| `POST` | `/api/cache/clear` | Empty the cache |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/webhooks` | List webhooks (secrets are never returned) |
| `POST` | `/api/webhooks` | Register a webhook |
| `GET` | `/api/webhooks/{webhook_id}` | One webhook |
| `PATCH` | `/api/webhooks/{webhook_id}` | Update url, events or active flag |
| `DELETE` | `/api/webhooks/{webhook_id}` | Remove a webhook |
| `GET` | `/api/webhooks/events` | Supported event names |

### Sharing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/share/create` | Create a share link |
| `GET` | `/api/share/list` | List share links |
| `GET` | `/api/share/{short_id}` | Resolve a share link |
| `GET` | `/api/share/{short_id}/stats` | Access statistics for a link |
| `POST` | `/api/share/{short_id}/deactivate` | Deactivate without deleting |
| `DELETE` | `/api/share/{short_id}` | Delete a share link |

### Plugins

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/plugins/list` | Discovered plugins and their state |
| `GET` | `/api/plugins/{plugin_name}` | Plugin detail |
| `POST` | `/api/plugins/install` | Install from a path or archive |
| `POST` | `/api/plugins/{plugin_name}/enable` | Enable |
| `POST` | `/api/plugins/{plugin_name}/disable` | Disable |
| `POST` | `/api/plugins/reload` | Re-scan the plugin directory |

### Cloud storage

Available when `S3_ENABLED` or `AZURE_BLOB_ENABLED` is configured.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cloud/providers` | Configured providers |
| `POST` | `/api/cloud/upload` | Upload a file |
| `POST` | `/api/cloud/upload-generation/{task_id}` | Upload a generation's output |
| `GET` | `/api/cloud/list/{provider}` | List stored files |
| `GET` | `/api/cloud/{provider}/url/{path}` | Signed URL for a file |
| `DELETE` | `/api/cloud/{provider}/{path}` | Delete a file |

### AI (optional)

Requires `OLLAMA_ENABLED=true` and a reachable Ollama instance.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai/health` | Whether the AI backend answers |
| `GET` | `/api/ai/models` | Models the backend offers |
| `POST` | `/api/ai/analyze` | Analyse generated terrain |
| `POST` | `/api/ai/recommendations` | Suggestions for an area |
| `POST` | `/api/ai/optimize-settings` | Suggested generation settings |

### WebSocket

| Path | Description |
|------|-------------|
| `/ws/generation/{task_id}` | Live progress events for one generation |

---

## 📦 Core models

### `MapGenerationRequest`

Body of `POST /api/generate`. `bbox` and `name` are required; everything else
has a default.

| Field | Type | Notes |
|-------|------|-------|
| `bbox` | object | `north`, `south`, `east`, `west` in degrees |
| `name` | string | Output directory name |
| `resolution` | int | Heightmap side in pixels |
| `export_formats` | string[] | See `GET /api/formats` |
| `elevation_source` | string | `auto` follows `ELEVATION_SOURCE_PRIORITY` |
| `enable_ai_analysis` | bool | Requires the AI backend |
| `enable_roads` | bool | Vector data via Overpass |
| `enable_buildings` | bool | Vector data via Overpass |
| `enable_vegetation` | bool | |
| `enable_water_bodies` | bool | |
| `enable_weightmaps` | bool | Engine splat/weight maps |
| `enable_3d_preview` | bool | |

Latitude is clamped to ±90 and longitude to ±180 at the model layer, so an
out-of-range value is rejected before any work starts.

---

## ❌ Error handling

Errors use FastAPI's standard envelope:

```json
{ "detail": "Task does-not-exist not found" }
```

Request validation fails with **422** and a per-field breakdown:

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "bbox", "north"],
      "msg": "Input should be less than or equal to 90",
      "input": 200
    }
  ]
}
```

The two middlewares answer in their own shape, with an `error` key — see
[Rate limiting](#rate-limiting) and [Authentication](#authentication).

| Status | Meaning |
|--------|---------|
| `400` | Malformed input that passed schema validation, e.g. an unsafe map name |
| `401` | Missing or invalid session token, or missing API key |
| `403` | Authenticated but not permitted, e.g. a non-admin on an admin route |
| `404` | Unknown task, map, cache key or webhook |
| `422` | Schema validation failed |
| `429` | Rate limit exceeded |
| `500` | Unhandled server error |

---

## ⏱️ Rate limiting

Enabled by default, with per-minute, per-hour and per-day budgets over a
sliding window:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000
```

Every response carries the remaining per-minute budget:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
```

Exceeding a budget returns **429** with `Retry-After`:

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 60 per minute",
  "retry_after": 60
}
```

Clients are identified by authenticated user id when available, otherwise by
socket address. `X-Forwarded-For` is ignored unless
`RATE_LIMIT_TRUST_FORWARDED_FOR=true`, because a client that can set the header
itself can otherwise rotate it to bypass the limit. `/health*` and `/metrics`
are exempt.

---

## 🔔 Webhooks

Register a URL and the events it should receive. `GET /api/webhooks/events`
returns the supported names:

```json
{ "events": ["generation.started", "generation.completed", "generation.failed"] }
```

Each delivery is a POST carrying:

```json
{
  "event": "generation.completed",
  "timestamp": "2026-07-26T22:48:23.503329",
  "data": { "task_id": "…", "name": "…" }
}
```

### Signature

Deliveries carry an HMAC-SHA256 of the **exact transmitted bytes**, keyed with
the webhook's secret:

```http
X-TerraForge-Signature: sha256=<hex>
```

Verify against the raw body — re-serializing the parsed JSON produces different
bytes and a signature that will not match:

```python
import hashlib
import hmac

def verify(request_body: bytes, signature: str, secret: str) -> bool:
    algorithm, _, digest = signature.partition("=")
    if algorithm != "sha256":
        return False
    expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)
```

The secret is supplied by the subscriber when registering the webhook
(16 characters minimum) and is write-only: no endpoint ever echoes it back.
`GET /api/webhooks` reports `has_secret` instead. Deliveries are retried with
exponential backoff, except on 4xx — a subscriber that rejected the payload
will reject the retry too.

Subscriptions are held in memory and do not survive a restart.

---

<div align="center">

[Back to Docs](README.md) • [Examples](API_EXAMPLES.md)

</div>
