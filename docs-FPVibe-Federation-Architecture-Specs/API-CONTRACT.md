# FPVibe — API Federation Contract

This document defines the JSON API contract between FPVibe federation tools.
It is the binding spec for cross-tool communication. Each tool implements its
side; consumers degrade gracefully when endpoints are unreachable.

Status: Draft v1.0 · companion to ARCHITECTURE.md

---

## 1. Conventions

### Base URLs

Each tool is discovered via environment variables. All URLs in this document
are relative to the base URL.

| Tool | Env var | Default | Example |
|------|--------|---------|---------|
| fpv-inventory | `INVENTORY_URL` | (unset = standalone) | `http://fpv-inventory:8000` |
| flowchart | `SESSIONS_URL` | (unset = standalone) | `http://flowchart:3000` |
| fpvibe-spots | `SPOTS_URL` | (unset = standalone) | `http://fpvibe-spots:7000` |

When a URL env var is unset or empty, the consumer tool operates without that
federation link. No calls are made; fallback behavior activates.

### Content type

All responses are `application/json; charset=utf-8`.

### Errors

Standard HTTP status codes:
- `200` — success
- `404` — entity not found
- `500` — server error (consumer should retry or degrade)

Error body (when the server can produce one):
```json
{ "error": "Part not found" }
```

Consumers must handle missing/empty/unset gracefully. A `404` on a cross-tool
fetch is not a crash — it means the referenced entity no longer exists.

### No authentication

No auth headers, no tokens, no sessions. Tools are local-only behind Runtipi.

---

## 2. Health endpoints

Every tool must expose:

```
GET /api/health
```

Response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "name": "fpv-inventory"
}
```

The `name` field identifies which tool is responding (useful for debugging
misconfigured env vars). The `version` is the tool's package version, used to
detect incompatible API versions when debugging.

---

## 3. fpv-inventory API

### 3.1 GET /api/builds

Returns top-level flyable assemblies. A "build" is a part where `parent_id IS NULL`
and `type = "craft"`.

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status: `unused`, `in-use`, `broken`, `retired`, `lost` |
| `q` | string | Case-insensitive name search |

**Response (200):**
```json
[
  {
    "id": 5,
    "name": "LionBee",
    "type": "craft",
    "status": "in-use",
    "quantity": 1,
    "specs": "FC: BetaFPV F4 1S\nMotors: 0702 30000KV\nFrame: Meteor65",
    "notes": "Power loops still mushy on exit",
    "photo_path": "5-1719504000.jpg"
  },
  {
    "id": 7,
    "name": "Air65III",
    "type": "craft",
    "status": "in-use",
    "quantity": 1,
    "specs": "FC: Super BF F4 AIO\nMotors: 0802 27000KV\nFrame: Air65",
    "notes": "",
    "photo_path": null
  }
]
```

**Empty array when no builds exist.** Not an error.

### 3.2 GET /api/builds/:id

Returns a single build with its component tree (one level deep — the BOM).

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | integer | Part ID of the build |

**Response (200):**
```json
{
  "id": 5,
  "name": "LionBee",
  "type": "craft",
  "status": "in-use",
  "quantity": 1,
  "specs": "FC: BetaFPV F4 1S\nMotors: 0702 30000KV\nFrame: Meteor65",
  "notes": "Power loops still mushy on exit",
  "photo_path": "5-1719504000.jpg",
  "parent_id": null,
  "created_at": "2026-01-15 10:30:00",
  "updated_at": "2026-07-04 18:22:00",
  "children": [
    {
      "id": 8,
      "name": "0702 Motor",
      "type": "motor",
      "status": "in-use",
      "quantity": 4,
      "specs": null,
      "notes": null
    },
    {
      "id": 12,
      "name": "BetaFPV F4 1S AIO",
      "type": "fc",
      "status": "in-use",
      "quantity": 1,
      "specs": "16MB blackbox, 5V BEC",
      "notes": "Betaflight 4.5.0"
    }
  ]
}
```

**404 when build not found:**
```json
{ "error": "Build not found" }
```

### 3.3 GET /api/builds/:id/bom

Returns the BOM for a build with part details and computed allocation. This is
the allocation mechanic: inventory reads its own parts and their parent-child
relationships (children ARE the BOM) to compute on-hand/allocated/free.

**Response (200):**
```json
[
  {
    "part_id": 8,
    "part_name": "0702 Motor",
    "part_type": "motor",
    "qty_in_build": 4,
    "role": null,
    "on_hand": 12,
    "allocated": 4,
    "free": 8
  },
  {
    "part_id": 12,
    "part_name": "BetaFPV F4 1S AIO",
    "part_type": "fc",
    "qty_in_build": 1,
    "role": null,
    "on_hand": 2,
    "allocated": 1,
    "free": 1
  }
]
```

**How allocation is computed:**

Parts are grouped by `name + type` to relate stock rows to installed rows. A single logical part (e.g. "0702 Motor") may have multiple rows: one or more top-level stock rows (`parent_id IS NULL`, `status: "unused"`) and one child row per build that installs it (`parent_id` pointing to the build, `status: "in-use"`). The grouping key is `name + type`.

**Grouping key constraint:** `name` is treated as a stable identifier within a type — parts are expected to use consistent naming across stock and installed rows (e.g. always "0702 Motor", not "0702 motor" or "0702Motor"). If disambiguation is needed, include vendor info in the name (e.g. "BetaFPV 0702 Motor"). Future versions may switch to a stable surrogate key if this proves fragile.

1. For each child part of the build, get `qty_in_build` from the child record's `quantity` field (how many of that part are installed in this build).
2. `on_hand` = total owned quantity = sum of `quantity` across ALL rows in the same name+type group (both top-level stock rows AND child rows installed in builds). This is the total quantity you own, regardless of where it is.
3. `allocated` = sum of `qty_in_build` across ALL builds that install this part — i.e., the `quantity` of every child row whose `parent_id` points to a build and whose name+type matches this part.
4. `free` = `on_hand` - `allocated` (= total owned minus total installed across all builds).

**Example:** You own 12 "0702 Motor" (8 in stock + 4 installed in LionBee). `on_hand` = 12, `allocated` = 4, `free` = 8 — matching the response example above and the reverse view in §3.6.

**Note on `role`:** the parts schema has no `role` column yet, and the children-are-the-BOM model has nowhere to store one — see open question §7.6. Until that's resolved, `role` is nullable and implementations return `null`, as the example above shows; once a source for the field exists, the intent is values like `"motors"` or `"fc-aio"`.

### 3.4 GET /api/parts

Returns all parts, optionally filtered by type. Gear items (`type: "gear"`)
are returned here for backward compatibility, but for gear-specific fields
(serial_number, warranty_expiry, etc.) use `/api/gear` (§3.7) instead.

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `type` | string | Filter by type: `motor`, `fc`, `esc`, `vtx`, `frame`, `camera`, `antenna`, `battery`, `craft`, `gear`, `other` |
| `status` | string | Filter by status |
| `parent_id` | integer | Filter by parent (0 = top-level only) |
| `q` | string | Case-insensitive name search |

**Response (200):**
```json
[
  {
    "id": 8,
    "name": "0702 Motor",
    "type": "motor",
    "status": "in-use",
    "quantity": 4,
    "parent_id": 5,
    "specs": null,
    "notes": null,
    "photo_path": null
  }
]
```

### 3.5 GET /api/parts/:id

Returns a single part with its history.

**Response (200):**
```json
{
  "id": 8,
  "name": "0702 Motor",
  "type": "motor",
  "status": "in-use",
  "quantity": 4,
  "specs": null,
  "notes": null,
  "photo_path": null,
  "parent_id": 5,
  "created_at": "2026-01-15 10:30:00",
  "updated_at": "2026-07-01 14:00:00",
  "history": [
    {
      "id": 1,
      "part_id": 8,
      "action": "created",
      "from_parent_id": null,
      "to_parent_id": 5,
      "old_status": null,
      "new_status": null,
      "quantity_delta": null,
      "notes": null,
      "created_at": "2026-01-15 10:30:00"
    },
    {
      "id": 5,
      "part_id": 8,
      "action": "updated",
      "from_parent_id": null,
      "to_parent_id": null,
      "old_status": "unused",
      "new_status": "in-use",
      "quantity_delta": 0,
      "notes": null,
      "created_at": "2026-01-20 09:00:00"
    }
  ]
}
```

### 3.6 GET /api/parts/:id/allocation

Returns where a specific part is allocated across all builds. This is the
reverse view of the BOM: "I have this part — where is it used?"

**Response (200):**
```json
{
  "part_id": 8,
  "part_name": "0702 Motor",
  "on_hand": 12,
  "allocated": [
    {
      "build_id": 5,
      "build_name": "LionBee",
      "qty": 4
    }
  ],
  "free": 8
}
```

Each build that installs the part appears as one entry in `allocated`. (In this
example dataset only LionBee installs the 0702 Motor — Air65III runs 0802 motors,
per §3.1 — so `allocated` has one entry and the totals match §3.3: `on_hand` 12,
`allocated` 4, `free` 8.)

**404 when part not found:**
```json
{ "error": "Part not found" }
```

### 3.7 GET /api/gear

Returns all gear items (discrete serial/warranty assets). Gear is the
discrete-asset counterpart to Parts — distinct by the fungible-vs-discrete
boundary. A bag of props is Parts; your goggles are Gear.

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status |
| `q` | string | Case-insensitive name search |

**Response (200):**
```json
[
  {
    "id": 4,
    "name": "DJI Goggles N3",
    "type": "gear",
    "status": "in-use",
    "quantity": 1,
    "serial_number": "SN-XXXXXXX",
    "warranty_expiry": "2027-03-15",
    "purchase_date": "2026-03-15",
    "purchase_price": 549.00,
    "specs": "O4 receiver, 1080p display",
    "notes": "",
    "photo_path": null,
    "parent_id": null
  }
]
```

**Empty array when no gear exists.** Not an error.

### 3.8 GET /api/gear/:id

Returns a single gear item with full details.

**Response (200):**
```json
{
  "id": 4,
  "name": "DJI Goggles N3",
  "type": "gear",
  "status": "in-use",
  "quantity": 1,
  "serial_number": "SN-XXXXXXX",
  "warranty_expiry": "2027-03-15",
  "purchase_date": "2026-03-15",
  "purchase_price": 549.00,
  "specs": "O4 receiver, 1080p display",
  "notes": "",
  "photo_path": null,
  "parent_id": null,
  "created_at": "2026-03-15 12:00:00",
  "updated_at": "2026-07-01 09:00:00",
  "history": [
    {
      "id": 1,
      "part_id": 4,
      "action": "created",
      "from_parent_id": null,
      "to_parent_id": null,
      "old_status": null,
      "new_status": null,
      "quantity_delta": null,
      "notes": "Purchased from GetFPV",
      "created_at": "2026-03-15 12:00:00"
    }
  ]
}
```

**404 when gear not found:**
```json
{ "error": "Gear not found" }
```

**Note:** Gear reuses the `parts` and `part_history` tables (gear is `type: "gear"` in the parts table). The `part_id` field in history entries refers to the gear item's own ID in the `parts` table — there is no separate `gear_id` or `gear_history` table.

### 3.9 GET /api/stock

Returns aggregated stock by type/status across all parts. This powers the
stock-check view.

**Response (200):**
```json
[
  {
    "type": "motor",
    "status": "in-use",
    "total_quantity": 8,
    "count": 2
  },
  {
    "type": "motor",
    "status": "unused",
    "total_quantity": 12,
    "count": 3
  },
  {
    "type": "fc",
    "status": "in-use",
    "total_quantity": 2,
    "count": 2
  },
  {
    "type": "battery",
    "status": "in-use",
    "total_quantity": 6,
    "count": 6
  }
]
```

---

## 4. flowchart API

### 4.1 GET /api/sessions

Returns flight sessions, most recent first.

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `craft` | integer | Filter by inventory craft ID (cross-tool link) |
| `craft_name` | string | Filter by platform name (legacy freetext match) |
| `limit` | integer | Max results (default: 50, max: 200) |

**Response (200):**
```json
[
  {
    "id": 42,
    "date": "2026-07-04",
    "location": "stoughton-field",
    "platform": "LionBee",
    "craft_inventory_id": 5,
    "pack_count": 6,
    "crash_count": 3,
    "session_type": "interleaved",
    "notes": "Power loops improving"
  },
  {
    "id": 41,
    "date": "2026-07-03",
    "location": "home-room-A",
    "platform": "Air65III",
    "craft_inventory_id": 7,
    "pack_count": 4,
    "crash_count": 1,
    "session_type": "blocked-drill",
    "notes": "Orbit lines tightening"
  }
]
```

**`craft_inventory_id`** is the cross-tool link — an integer referencing an
fpv-inventory part ID. It is nullable: sessions created without inventory
federation use the `platform` freetext field only.

### 4.2 GET /api/sessions/:id

Returns a full session with packs, trick attempts, crashes, and review.

**Response (200):**
```json
{
  "id": 42,
  "date": "2026-07-04",
  "time_start": "14:00",
  "time_end": "16:30",
  "location": "stoughton-field",
  "platform": "LionBee",
  "craft_inventory_id": 5,
  "weather": "5-8mph",
  "session_type": "interleaved",
  "notes": "Power loops improving",
  "packs": [
    {
      "id": 101,
      "pack_number": 1,
      "voltage_start": 4.35,
      "voltage_end": 3.50,
      "focus": "Power loops",
      "crashes": 1,
      "notes": ""
    }
  ],
  "trick_attempts": [
    {
      "id": 201,
      "trick_id": 3,
      "trick_name": "Power Loop",
      "attempts": 8,
      "landed": 5,
      "notes": "Mushy on exit"
    }
  ],
  "crashes": [
    {
      "id": 301,
      "pack_number": 1,
      "trick_id": 3,
      "trick_name": "Power Loop",
      "failure_type": "throttle",
      "root_cause": "pilot",
      "action_item": "Blip throttle earlier on exit"
    }
  ],
  "review": {
    "good_1": "Orbit lines tightening",
    "good_2": "Power loop commitment better",
    "good_3": "",
    "improve_1": "Exit the power loop cleaner",
    "improve_2": "",
    "improve_3": "",
    "fatigue": "good",
    "frustration": "mild",
    "stopped_before_bad": true,
    "tomorrow_focus": "Power loop exit timing"
  }
}
```

**404 when session not found:**
```json
{ "error": "Session not found" }
```

### 4.3 Existing endpoints (unchanged)

These flowchart endpoints already exist and remain as-is:

- `GET /api/health` — health check
- `GET /api/tricks` — all tricks (reference data)
- `GET /api/tricks/drills/all` — drill list
- `GET /api/tricks/resources/all` — learning resources
- `GET /api/tricks/schedule/all` — 20-week schedule
- `GET /api/progress/stats` — overall statistics
- `GET /api/progress/mastery` — trick mastery overview
- `GET /api/progress/gates` — phase gate checks
- `GET /api/equipment` — equipment inventory (flowchart-local)
- `GET /api/data/export` — full JSON export

### 4.4 Required addition: `craft_inventory_id` on sessions

flowchart's `sessions` table needs a new nullable integer column:

```sql
ALTER TABLE sessions ADD COLUMN craft_inventory_id INTEGER;
```

This column stores the fpv-inventory part ID when a session is linked to an
inventory build. When null, the session uses the legacy `platform` freetext
field. Migration is additive — existing sessions are unaffected.

The `GET /api/sessions` response already includes this field in the shape
above. The `GET /api/sessions/:id` response includes it too.

---

## 5. Degradation patterns

### 5.1 Consumer: flowchart fetching builds from inventory

```typescript
// In flowchart's session form — fetching the craft dropdown.
// This code runs in the browser (note localStorage below). INVENTORY_URL
// originates as a server-side env var on flowchart (Node/Hono) and must be
// handed to the client — e.g. injected into the page at render time or served
// from a tiny /api/config endpoint. How it's exposed, and whether the browser
// can reach the Docker-internal hostname at all, is open question §7.7.

const INVENTORY_URL =
  (window as Window & { FPVIBE_CONFIG?: { INVENTORY_URL?: string } })
    .FPVIBE_CONFIG?.INVENTORY_URL ?? "";

async function fetchBuilds(): Promise<Build[] | null> {
  if (!INVENTORY_URL) return null;  // federation disabled

  try {
    const res = await fetch(`${INVENTORY_URL}/api/builds`, {
      signal: AbortSignal.timeout(3000),  // 3s timeout — localhost should be instant
    });
    if (!res.ok) return null;
    const builds = await res.json();

    // Cache for offline fallback
    localStorage.setItem("fpvibe:builds", JSON.stringify(builds));
    return builds;
  } catch {
    // Network error, timeout, or JSON parse failure — degrade
    return null;
  }
}

function getCachedBuilds(): Build[] {
  try {
    return JSON.parse(localStorage.getItem("fpvibe:builds") ?? "[]");
  } catch {
    return [];
  }
}

// In the form:
const builds = await fetchBuilds();
const cachedBuilds = getCachedBuilds();

let status: "live" | "cached" | "offline";
let dropdownOptions: string[];

if (builds && builds.length >= 0) {
  status = "live";
  dropdownOptions = builds.map(b => b.name);
} else if (cachedBuilds.length > 0) {
  status = "cached";
  dropdownOptions = cachedBuilds.map(b => b.name);
} else {
  status = "offline";
  dropdownOptions = ["Air65III", "Mobula6", "Meteor75", "Rekon3", "5-inch", "sim-whoop", "sim-5inch", "custom"];
  // Fall back to existing static enum
}

// Show badge: "✓ inventory" / "⚠ cached (N min ago)" / "⚠ offline"
// Session is always creatable regardless of status
```

### 5.2 Consumer: inventory fetching sessions from flowchart

```typescript
// In fpv-inventory's build detail page — "last flown" section

const SESSIONS_URL = Deno.env.get("SESSIONS_URL") ?? "";

async function fetchRecentSessions(craftId: number): Promise<Session[] | null> {
  if (!SESSIONS_URL) return null;

  try {
    const res = await fetch(
      `${SESSIONS_URL}/api/sessions?craft=${craftId}&limit=5`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// In the build detail template:
const sessions = await fetchRecentSessions(part.id);
const lastFlownSection = sessions && sessions.length > 0
  ? renderSessionList(sessions)
  : "";  // empty string = section hidden entirely
```

### 5.3 Degradation contract

| Situation | Behavior |
|-----------|----------|
| Sibling URL env var unset | No calls made. Feature hidden or fallback used. |
| Sibling container down (connection refused) | Timeout after 3s. Use cache or fallback. Show "⚠ offline" badge. |
| Sibling returns 404 for specific entity | Reference is stale. Show "entity no longer exists" or hide reference. Do not crash. |
| Sibling returns 500 | Same as connection refused — degrade to cache/fallback. |
| Sibling returns valid but empty array | This is success with no data. Show "no builds found" / "no sessions found". Not an error. |
| Sibling returns malformed JSON | Treat as connection failure. Degrade. |

**Hard rule: a cross-tool fetch failure must never prevent a save.**
If flowchart can't reach inventory, the session is still created — it just
won't have a `craft_inventory_id` linked. If inventory can't reach flowchart,
the build detail page still renders — it just hides the "last flown" section.

---

## 6. Versioning

### 6.1 API versioning

Each tool's `/api/health` returns its `version`. The federation contract is
this document. When an endpoint's response shape changes in a breaking way:

1. Bump the tool version (semver).
2. Note the breaking change in the docs repo (`docs/CHANGELOG.md`).
3. Update this document with the new shape.

There is no automated version negotiation. For n=1, you'll notice breakage
when you use the feature. The `version` field in `/api/health` helps you
confirm which version is running when debugging.

### 6.2 Contract version

This document is versioned: `v1.0`. Future versions will add endpoints (additive)
or change response shapes (breaking). Additive changes don't require consumer
updates. Breaking changes are noted in the changelog.

---

## 7. Open API questions

1. **Should flowchart accept `craft_inventory_id` on POST /api/sessions?**
   Currently the session create endpoint accepts `platform` (string). Adding
   `craft_inventory_id` (integer, nullable) to the POST body is the natural
   extension. This is in the Phase 2 implementation scope.

2. **Should inventory expose a "create build from components" endpoint?**
   `POST /api/builds` accepting a name + array of part IDs to assemble as
   children. This supports the "from-the-bin builds" feature. Needs design
   — it's the first cross-tool write concern, but it stays within inventory
   (inventory writes to its own DB; flowchart just calls the API).

3. **Should there be a unified search across tools?**
   `GET /api/search?q=power+loop` across sessions, builds, tricks? Probably
   not worth it for n=1. Each tool's own search is sufficient.

4. **Should the blackbox skill expose an API?**
   The skill runs inside Claude Code / Hermes, not as a server. But it could
   expose an MCP server with `decode`, `analyze`, `compare` as callable tools.
   This would let flowchart or inventory trigger blackbox analysis via MCP
   rather than requiring the user to invoke the skill manually. Likely a
   future enhancement, not a Phase 1 concern.

5. **Should gear packing lists be exposed via API?**
   If packing lists live in flowchart, they'd be `GET /api/packing-lists?session_type=whoop`.
   If they live in inventory, they'd be under inventory's API. Depends on
   decision #6 in ARCHITECTURE.md (which tool owns packing lists).

6. **Where does the BOM `role` field come from?**
   `GET /api/builds/:id/bom` (§3.3) returns a `role` field, but the parts table
   has no role column and the children-are-the-BOM model has nowhere to store
   one. Options: (a) drop the field — `part_type` conveys nearly the same
   signal for n=1; (b) derive it from the child part's `type`; (c) add an
   optional `role` column set when a part is installed into a build (allows
   e.g. two cameras distinguished as main/backup). Until decided,
   implementations return `null` (§3.3 note).

7. **Browser-reachable URLs and CORS.**
   The `INVENTORY_URL` / `SESSIONS_URL` examples use Docker-network hostnames
   (`http://fpv-inventory:8000`) that resolve container-to-container but not
   from the user's browser — yet §5.1's craft-dropdown fetch runs client-side
   (it uses localStorage), and the ARCHITECTURE.md §5.3 cross-tool links are
   clicked in a browser. Either (a) each tool's server proxies cross-tool reads
   and rendered links use browser-reachable (Runtipi/tailnet) hostnames, or
   (b) tools serve CORS headers and env config splits into internal vs
   browser-facing base URLs — prefer an explicit allowlist of sibling origins
   over `Access-Control-Allow-Origin: *`, since with no auth a wildcard would
   let any website the user's browser visits read these local APIs. Decide
   before Phase 2 — it dictates where the degradation logic lives.