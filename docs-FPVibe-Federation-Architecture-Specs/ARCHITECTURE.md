# FPVibe — Architecture Spec v1.0

Status: Draft · supersedes FPVIBE.md v0.3
Audience: implementing agents (Claude Code, opencode, Hermes) and future-Cori

---

## 1. TL;DR

FPVibe is a federation of single-purpose, self-hosted FPV tools. Each tool is an independent Docker container with its own SQLite database and web UI. Tools integrate via lightweight JSON APIs — never via a shared database, shared filesystem, or shared git substrate. Non-container members (skills, static sites) join by adopting naming, theme, and link conventions.

**The federation contract is an API schema, not a file format.**

- Each tool owns its data, its database, its deploy lifecycle.
- Each tool exposes `GET /api/<entity>` for entities other tools reference.
- Each tool discovers siblings via env vars (`INVENTORY_URL`, `SESSIONS_URL`).
- Cross-tool calls are read-only, optional, and always degradable.
- No tool writes to another tool's database. Ever.
- No auth, no multi-tenancy. Local-only behind Runtipi's reverse proxy.
- Skills and static sites join by convention (naming, theme, links), not by API.

---

## 2. What Changed from v0.3

| v0.3 premise | v1.0 reality |
|---|---|
| Git is the single source of truth (YAML substrate) | Each tool owns its own SQLite database, edited through its own web UI |
| Commit-on-save; tools are views over text files | Normal database writes; tools are the editors |
| `fpv:` URN scheme + resolver service | Direct HTTP URLs (`http://fpv-inventory:8000/api/builds/3`) |
| Forward-auth proxy / tailnet perimeter auth | No auth. Local-only behind Runtipi. |
| Shared theme tokens file (`fpvibe-theme.css`) | Optional. Each tool uses similar CSS. No shared file required for n=1. |
| Meta-compose orchestration | Per-tool Runtipi entries. No meta-compose needed. |
| Conformance checklist with 8 gates | Simplified to 5 gates (§6). |
| Blackbox skill not mentioned | Blackbox skill is a federation citizen (non-container) via plugin marketplace |
| Gear packing lists not mentioned | Gear packing lists are a planned feature in the implementation plan |

**What survived:** federation over monolith, promote-don't-pre-build, independent deployability, graceful degradation, one-job-per-tool.

---

## 3. Current Repos, Tools, and Maturity

### Containerized tools

| Repo | Stack | Maturity | Database |
|------|-------|----------|----------|
| `FPVibe/flowchart` | Hono/Node + vanilla JS PWA | Working app, CI, multi-agent dev | SQLite (`better-sqlite3`) |
| `FPVibe/fpv-inventory` | Deno + server-rendered HTML | Functional, basic | SQLite (Deno `sqlite`) |

### Static tools (no server-side federation)

| Repo | Stack | Maturity | Data |
|------|-------|----------|------|
| `FPVibe/fpv-tools` | Vanilla JS, static PWA | Mature, public on Pages | Client-side only (igow.db via sql.js, localStorage) |
| `FPVibe/fpvibe.github.io` | — | Empty | — |

### Skills and non-container members

| Artifact | Type | Maturity | Distribution |
|----------|------|----------|-------------|
| **betaflight-blackbox** | Claude Code / Hermes skill | Active, daily use | Plugin marketplace (`fpvibe/skills` or `cori/fpv`), `.claude-plugin/marketplace.json` — Hermes reads this natively |
| **drone-mesh-mapper** | Hardware + firmware | Built, functional | Independent; tangential to federation. Could reference Spot entities via API if airspace-awareness features are added. |
| **IGOW challenge archive** | Static dataset | Complete (144 entries, seasons 1–6) | Currently `igow/igow.db` in fpv-tools (client-side SQLite via sql.js). Maps to Training entity if training promotes to its own tool. |
| **Gear packing lists** | Designed, not implemented | Architecture complete | Would live inside flowchart or inventory. Two bags (whoop, acro/long-range), composable session-type-based checklists, tier system (core/conditional/bench). |

### Org infrastructure

| Repo | Purpose |
|------|---------|
| `FPVibe/docs` | This document + API contract + historical specs |
| `FPVibe/.github` | Org-level profile and defaults |

**flowchart** is the most mature containerized tool: full JSON REST API, 25KB seed data, session/progress/tricks/equipment/denver/plans/export-import. Known gap: offline writes fail (ISSUE-offline-first.md).

**fpv-inventory** is functional but has no JSON API — pure server-rendered HTML form POSTs. Hierarchical parts (parent_id = assemblies), status, quantity, type, specs, photos, full history log. README is still template boilerplate.

**fpv-tools** is a static PWA with three tools (CLI Merge, Rate Profile, IGOW Reference). Client-side only. Does not participate in server-side federation. Can deploy dual: GitHub Pages for public reach, nginx container in Tipi for private-behind-Tailscale access. Same artifact does both.

**betaflight-blackbox** is an active skill for decoding and analyzing Betaflight blackbox logs. Components: decode.sh, analyze.py, turtle-mode classifier, cell count auto-detection, per-session triage. Key capabilities: tune health checks, motor balance, voltage sag profiling, RPM/desync investigation, gyro noise/filter analysis, crash forensics, flight comparison. The skill is LLM-powered — a standalone deployment either loses the analysis or requires hosting an LLM endpoint, which is a non-starter. The skill stays where the model already is (Claude Code, or Hermes Agent with a local model via Ollama). Distribution: plugin marketplace repo (`fpvibe/skills` or `cori/fpv`) with `.claude-plugin/marketplace.json`, which both Claude Code and Hermes read natively. Competitive landscape: Betaflight's native Chirp Signal Generator (BF 2025.12+) and upcoming autotune analysis page narrow the differentiation window.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Runtipi (Docker, local-only, no auth)                      │
│                                                             │
│  ┌──────────────┐       ┌──────────────────┐               │
│  │ flowchart    │       │ fpv-inventory    │               │
│  │ :3000        │       │ :8000            │               │
│  │              │       │                  │               │
│  │ SQLite:      │       │ SQLite:          │               │
│  │  sessions    │       │  parts           │               │
│  │  packs       │       │  part_history    │               │
│  │  tricks      │       │                  │               │
│  │  crashes     │       │                  │               │
│  │  reviews     │       │ JSON API (add):  │               │
│  │  equipment   │       │  GET /api/builds │               │
│  │              │       │  GET /api/parts  │               │
│  │ JSON API:    │  ───► │  GET /api/gear   │               │
│  │  GET /api/   │ fetch │  GET /api/stock  │               │
│  │  sessions    │ builds│                  │               │
│  └──────────────┘       └──────────────────┘               │
│         │                       │                          │
│         │  optional reverse      │                          │
│         │  (last flown)          │                          │
│         ◄───────────────────────│                          │
│                                                             │
│  ┌──────────────────────────────────────────┐              │
│  │ fpv-tools (static)                       │              │
│  │ GitHub Pages (public) and/or              │              │
│  │ nginx container in Tipi (private)         │              │
│  │ Client-side only, no server federation    │              │
│  └──────────────────────────────────────────┘              │
│                                                             │
│  Discovery: INVENTORY_URL / SESSIONS_URL env vars          │
│  No shared database, no shared filesystem                  │
│  No auth, no multi-tenancy                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Skills (non-container federation members)                  │
│                                                             │
│  ┌────────────────────┐    ┌──────────────────────────┐    │
│  │ betaflight-blackbox │    │ Plugin marketplace repo  │    │
│  │ (skill)             │───│  fpvibe/skills or cori/fpv│    │
│  │                     │    │ .claude-plugin/           │    │
│  │ Runs in: Claude Code│    │   marketplace.json        │    │
│  │ or Hermes+Ollama    │    │                           │    │
│  │                     │    │ Read by: Claude Code,     │    │
│  │ Joins by: naming,  │    │ Hermes (natively)         │    │
│  │ theme, link convs   │    │                           │    │
│  └────────────────────┘    └──────────────────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────┐              │
│  │ drone-mesh-mapper (tangential)            │              │
│  │ Hardware: XIAO ESP32-S3 + Heltec LoRa V3  │              │
│  │ Could reference Spot entities via API     │              │
│  │ Independent lifecycle, not a citizen      │              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Data ownership

Each entity has exactly one authoritative owner. Other tools read via API; they never write.

| Entity | Owner | Authority |
|--------|-------|-----------|
| Session (flight log) | flowchart | flowchart is the only writer |
| Pack, Trick attempt, Crash, Review | flowchart | flowchart |
| Build / Craft (flyable assembly) | fpv-inventory | inventory is the only writer |
| Part (component, spare, consumable) | fpv-inventory | inventory |
| Gear (discrete serial/warranty asset) | fpv-inventory | inventory |
| Spot (flying location) | flowchart | flowchart (until promoted to own tool) |
| Training plan / Drill | flowchart | flowchart (until promoted) |

### Graceful degradation

Cross-tool calls are always read-only and always degradable. The pattern:

```
flowchart session form → craft dropdown:
  1. Try GET {INVENTORY_URL}/api/builds
  2. If success: populate dropdown, cache result in localStorage
  3. If INVENTORY_URL unset or fetch fails:
     a. Use cached builds from last successful fetch
     b. If no cache: fall back to a static enum or freetext input
  4. Show a badge: "✓ inventory" / "⚠ cached" / "⚠ offline"
  5. Session is always creatable regardless of inventory state
```

```
fpv-inventory build detail → "last flown" section:
  1. Try GET {SESSIONS_URL}/api/sessions?craft=<id>&limit=5
  2. If success: show recent sessions with dates
  3. If SESSIONS_URL unset or fetch fails: hide the section
  4. Build detail page is fully functional without it
```

**Rule: core functionality of a tool never breaks because a sibling is down.**
Cross-tool features degrade to cached data → fallback input → silent omission.
Never to a crash, never to a blocked save.

---

## 5. The Federation Contract

### 5.1 Discovery

Each tool reads sibling URLs from environment variables:

| Env var | Points to | Required? |
|---------|-----------|-----------|
| `INVENTORY_URL` | fpv-inventory base URL (e.g. `http://fpv-inventory:8000`) | No — unset = no federation |
| `SESSIONS_URL` | flowchart base URL (e.g. `http://flowchart:3000`) | No |
| `SPOTS_URL` | fpvibe-spots base URL (future) | No |

When unset, the tool operates standalone. Federation is opt-in per tool.

### 5.2 Required API endpoints

Each tool that owns an entity that other tools reference **must** expose a read-only JSON API:

**fpv-inventory must add:**

```
GET /api/builds
  → Top-level assemblies (parent_id IS NULL, type = "craft")
  → [{ id, name, status, type, quantity, specs, notes, photo_path }]

GET /api/builds/:id
  → Single build with its component tree (the BOM)
  → { id, name, status, ... , children: [{ id, name, type, quantity, status }] }
  → (children shown as minimum subset; full child shape: see API-CONTRACT.md §3.2)

GET /api/builds/:id/bom
  → BOM with part details + computed allocation
  → [{ part_id, part_name, part_type, qty_in_build, role, on_hand, allocated, free }]

GET /api/parts
  → All parts including gear (optional ?type= filter; gear returned for backward compatibility, gear-specific fields via /api/gear)
  → [{ id, name, status, type, quantity, parent_id }]

GET /api/parts/:id
  → Single part with history (full shape: see API-CONTRACT.md §3.5)

GET /api/parts/:id/allocation
  → Where this part is allocated across all builds
  → { part_id, on_hand, allocated: [{ build_id, build_name, qty }], free }

GET /api/gear
  → All gear items (discrete serial/warranty assets)
  → [{ id, name, type, serial_number, warranty_expiry, purchase_date, ... }]

GET /api/gear/:id
  → Single gear item with full details

GET /api/stock
  → Aggregated stock by type/status across all parts
  → [{ type, status, total_quantity, ... }]

GET /api/health
  → { status: "ok", version: "x.y.z", name: "fpv-inventory" }
```

**flowchart already has:**

```
GET /api/sessions
  → Query: ?craft=<id>&limit=<n>
  → [{ id, date, location, platform, pack_count, crash_count }]

GET /api/sessions/:id
  → Full session with packs, tricks, crashes, review

GET /api/health
  → { status: "ok", version: "x.y.z", name: "flowchart" }
```

### 5.3 Link convention

Cross-tool links are plain HTTP URLs, not custom URN schemes:

- In flowchart UI: "Craft: [LionBee](http://fpv-inventory:8000/parts/5)" — direct link to inventory's build detail
- In inventory UI: "Last flown: [2026-07-04](http://flowchart:3000/#session=42)" — direct link to session detail

No resolver service. No `fpv:` scheme. The URL IS the link.

### 5.4 Versioning

Each tool's JSON API is versioned via the `version` field in `/api/health`.
The federation contract is this document. When an endpoint's response shape changes, bump the tool version and note the breaking change in the docs repo.

No automated compatibility checking. For n=1, breakage is caught when you use it.

---

## 6. Conformance — what makes a tool an FPVibe citizen

### Containerized tools

A containerized tool is in the federation iff:

1. **One job.** Doing two things → it's two tools.
2. **Owns its data.** SQLite in its container. No shared database, no shared filesystem.
3. **Exposes a JSON read API** for entities other tools reference.
4. **Degrades gracefully** when siblings are down. Core function never depends on a sibling being reachable.
5. **Docker + Runtipi-compatible.** Single container, single port, non-root (UID 1000), `/api/health` endpoint, env-configured, volume for `/data`.

### Non-container members (skills, static sites)

Skills and static sites join by convention, not by API:

1. **One job.** Same as containerized tools.
2. **Adopts naming conventions.** Consistent terminology. New and promoted containerized tools use the `fpvibe-*` prefix (e.g. `fpvibe-spots`, `fpvibe-training`); existing containers (`flowchart`, `fpv-inventory`) are grandfathered. Non-container members (skills, static sites, hardware) keep their existing names — the prefix convention applies to deployable containers, not to skills or reference data.
3. **Adopts theme tokens.** Uses the Multiboard-derived palette (§9) where applicable.
4. **References entities by URL or ID.** A prop-pitch calculator references Part and Craft entities; the blackbox skill references Session entities.
5. **Distributed via the plugin marketplace** (for skills) or GitHub Pages / Tipi nginx (for static tools).

Optional but recommended for all members: mobile-responsive, dark theme, PWA installable.

---

## 7. Entity Model

The entity model from v0.3 survives as a shared API schema reference. It's no longer a file format — it's what the JSON API responses look like.

### Build / Craft

A flyable aircraft. In inventory, it's a top-level part (parent_id IS NULL) with type = "craft" and child components (the BOM).

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
  "children": [
    { "id": 8, "name": "0702 Motor", "type": "motor", "quantity": 4, "status": "in-use" },
    { "id": 12, "name": "BetaFPV F4 1S", "type": "fc", "quantity": 1, "status": "in-use" }
  ]
}
```

### Part

An inventory item — component, spare, or consumable. Same `parts` table, just not type = "craft" or not top-level.

**The Part/Gear boundary is fungible-vs-discrete.** A bag of props is Parts (fungible quantity); your goggles are Gear (discrete, serial-numbered, warranty-bearing). DIY accessories are Parts unless they grow a serial/warranty you actually track.

### Gear

A discrete, serial/warranty-bearing asset — commercial craft, radios, goggles, the printer, the CNC. This is the DumbAssets-shaped slice. Gear is richer than a Part: it carries serial number, warranty expiry, purchase date, and optionally purchase price.

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
  "parent_id": null
}
```

Gear may keep a private JSON store for warranty tracking, but the canonical record is in the SQLite database, accessible via the JSON API.

### Session

A flight outing. Owned by flowchart.

```json
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
}
```

The `craft_inventory_id` field is the cross-tool link — it references an fpv-inventory part ID. It's optional; sessions created without inventory federation use the `platform` freetext field instead.

### Spot

A flying location. Currently a `location` enum in flowchart's session table. Promotes to its own tool only when airspace/compliance metadata outgrows a simple field.

### Training plan / Drill

Structured practice. Currently trick/drill seed data in flowchart. The IGOW challenge archive (144 entries, seasons 1–6, currently a static SQLite file in fpv-tools) maps to this entity. If training promotes to its own tool, the IGOW data could move from client-side `igow.db` into the training tool's database. Until then, it stays as static reference data in fpv-tools.

---

## 8. Promotion

Spots and training start as fields/tables inside flowchart. Promote to their own citizens only when a concrete trigger fires:

- **Spot → fpvibe-spots:** when airspace/compliance metadata (LAANC, IAA/MySRS registration, EU constraints) outgrows a `location` enum field and wants real structure/validation.
- **Training → fpvibe-training:** when drills need genuine progress tracking, streaks, or scheduling rather than a reference checklist. The IGOW archive (144 entries) would migrate from fpv-tools' client-side `igow.db` into the training tool's database at this point.

Promotion is cheap: add `SPOTS_URL` env var, stand up the new container, migrate the data. Existing sessions still reference the old location enum; new sessions can use the API. No link migration needed because there's no URN scheme — just update the env var.

---

## 9. Deploy and look

### Deploy shape (per containerized tool)

```
Dockerfile:
  - single container, non-root (UID 1000)
  - SQLite file at /data/<tool>.db
  - /api/health endpoint

docker-compose.yml:
  - single service
  - one port
  - volume: /data
  - env: PORT, DB_PATH, INVENTORY_URL (or SESSIONS_URL), NODE_ENV/DENO_ENV

Runtipi:
  - config.json entry in app store
  - exposable: true
  - no_auth: true
```

### Static tools (fpv-tools)

fpv-tools deploys dual:
- **GitHub Pages** for public reach (current: `cori.github.io/fpv-tools`, planned: `fpvibe.github.io`)
- **nginx container in Tipi** for private-behind-Tailscale access (optional, same artifact)

The same build artifact serves both. No server-side federation; client-side only.

### Skills (betaflight-blackbox)

Distributed via plugin marketplace repo (`fpvibe/skills` or `cori/fpv`):
- `.claude-plugin/marketplace.json` manifest
- Read natively by both Claude Code and Hermes Agent
- Hermes is model-agnostic → skill can run with a local model via Ollama
- The "I won't host an LLM" blocker becomes a quality question: is a local model sharp enough for tune analysis?

### Look and theme

Recommended palette seeded from Cori's Multiboard physical bench scheme:

| Token | Hex | Role |
|-------|-----|------|
| primary | `#9ecae1` | Light blue |
| secondary | `#9e7bb5` | Purple |
| accent | `#f08a3c` | Tangerine |

Each tool uses similar CSS. No shared theme file required for n=1 — just use the same hex values. Light/dark with persisted preference. Dark theme default (FPV pilots are used to dark UIs from Betaflight/goggles).

---

## 10. Implementation priorities

### Phase 1: Inventory JSON API (unblocks federation)

1. Add JSON API routes to fpv-inventory alongside existing HTML routes
2. Add `GET /api/builds`, `GET /api/builds/:id`, `GET /api/builds/:id/bom`, `GET /api/parts`, `GET /api/parts/:id`, `GET /api/parts/:id/allocation`, `GET /api/gear`, `GET /api/gear/:id`, `GET /api/stock`, `GET /api/health`
3. Add Gear as a richer entity (serial_number, warranty_expiry, purchase_date, purchase_price fields)
4. Acceptance: `curl http://localhost:8000/api/builds` returns JSON array; `curl http://localhost:8000/api/stock` returns aggregated quantities

### Phase 2: flowchart federation client

1. Add `INVENTORY_URL` env var support to flowchart
2. Replace hardcoded `platform` enum in session form with dynamic fetch from `{INVENTORY_URL}/api/builds`
3. Implement degradation: fetch → cache → fallback enum → freetext
4. Store `craft_inventory_id` (integer, nullable) on sessions that link to inventory builds
5. Acceptance: session form populates craft dropdown from inventory; if inventory is down, falls back gracefully

### Phase 3: Inventory reverse reference (optional)

1. Add `SESSIONS_URL` env var support to fpv-inventory
2. On build detail page, fetch recent sessions for that craft from flowchart
3. Acceptance: build detail shows "last flown" section; degrades to hidden when flowchart is down

### Phase 4: Inventory features (user-requested)

1. **Stock check view:** aggregate quantities by type/status across all parts (uses `GET /api/stock`)
2. **Repair plan entity:** link a broken part to needed replacement parts + status tracking
3. **From-the-bin builds:** guided assembly flow — pick components from inventory, create a new craft with those parts as children
4. **Allocation mechanic:** inventory computes on-hand/allocated/free by reading its own parts + their parent-child relationships (children ARE the BOM). Report `on hand / allocated / free` per part.
5. Acceptance: stock check shows "motors: 12 unused, 8 in-use" (the by-type/status aggregation of `GET /api/stock`); a part's allocation reports on-hand/allocated/free per part (e.g. "0702 Motor: 12 on hand, 4 allocated, 8 free", matching API-CONTRACT.md §3.3/§3.6); repair plan links broken motor to replacement; from-the-bin creates a new craft in inventory

### Phase 5: Gear packing lists

1. Implement the designed gear packing architecture, translated to v1.0: the original design (a `gear/` directory of component files, a `sessions/` directory of profiles, a `bin/pack` generator) predates the SQLite/API model — keep its composition model (components → session-type profiles → generated tickbox checklist) but store components and profiles as tables in the owning tool, not as files
2. Two bags: whoop bag (1S analog, indoor/micro) and acro/long-range bag (5" freestyle, 3", LR)
3. Each item carries a justification field and a tier (core, conditional, bench)
4. Lives inside flowchart or inventory (decision: which tool owns packing lists?)
5. Acceptance: packing list generates a tickbox checklist for a given session type

### Phase 6: Plugin marketplace + blackbox skill

1. Create `fpvibe/skills` (or `cori/fpv`) repo with `.claude-plugin/marketplace.json`
2. Add betaflight-blackbox skill as the first marketplace entry
3. Verify Hermes reads the marketplace manifest natively
4. Acceptance: `hermes skills install fpvibe/betaflight-blackbox` (or equivalent) works; skill runs with local model via Ollama

### Phase 7: Documentation reconciliation

1. Replace FPVIBE.md v0.3 with this ARCHITECTURE.md in docs repo (this PR)
2. Update fpvibe-context.md to reflect actual repo state (org exists, repos transferred, fpv-inventory has JSON API, blackbox skill is a citizen, gear packing lists are planned)
3. Fix fpv-inventory README (still template boilerplate)
4. Migrate fpv-tools from `cori.github.io/fpv-tools` to `fpvibe.github.io`
5. Fold in the inventory collation doc's source thread provenance

---

## 11. Guardrails (anti-patterns)

- **No shared database.** Each tool's SQLite is its own. Never mount the same file into two containers.
- **No shared filesystem / git substrate.** Data lives in databases, edited through web UIs.
- **No cross-tool writes.** Tools read siblings via API; they never write to a sibling's database.
- **No plugin framework.** No shared "core" library beyond conventions documented here.
- **No auth.** Local-only behind Runtipi. No login, no sessions, no user store.
- **No multi-tenancy.** Single user. No ownership fields, no ACLs.
- **No hard runtime dependencies.** Each tool boots and functions standalone. Federation is opt-in via env vars.
- **Keep tools single-job.** If one grows a second job, split it.
- **When in doubt, ship a small tool — not a bigger one.**
- **Skills don't need containers.** The blackbox skill joins by convention, not by deployment. Don't force a container where a skill suffices.

---

## 12. Open decisions

1. **Does flowchart's `equipment` table go away, or does it become session-event-only?** Inventory owns "what exists"; flowchart should own "what happened during a session." The equipment_log table (which already links to session_id) might become the canonical equipment-event record, while inventory owns the part itself. Decide before Phase 2.

2. **Gear: add `gear` type to enum or `is_gear` flag?** The collation doc recommends: commercial / serial-warranty-bearing only to start. DIY accessories are fungible → they're Parts. Promote an accessory to Gear only if it grows a serial/warranty you actually track. This keeps the Part/Gear line crisp. (Recommendation: add `gear` type to the enum. Gear gets its own response shape with serial/warranty fields.)

3. **Tune profiles:** Where do Betaflight tune/rate profiles live? In inventory (as a field on a craft), in flowchart (as a session reference), or in a future fpvibe-tune tool? For now, tune data is in fpv-tools' rate-profile localStorage. No server-side home yet. The blackbox skill can reference tune data during analysis but doesn't store it.

4. **fpv-tools → fpvibe.github.io migration:** The org Pages repo exists but is empty. fpv-tools still deploys to `cori.github.io/fpv-tools`. Worth migrating for namespace consistency, but breaks existing bookmarks/links.

5. **IGOW reference data:** Currently a static SQLite file in fpv-tools (`igow/igow.db`). If training promotes to its own tool, should this data move into the training tool's database, or stay client-side? Recommendation: stay client-side until training promotes — it's reference data, not session data.

6. **Gear packing lists: flowchart or inventory?** The designed architecture uses Gear and Session entities. Gear lives in inventory; sessions live in flowchart. The packing list composes from both. Which tool owns the packing list UI? Recommendation: flowchart, since packing is session-type-driven and flowchart owns sessions.

7. **Plugin marketplace repo name:** `fpvibe/skills` (org-level, consistent with other repos) vs `cori/fpv` (personal, established). Recommendation: `fpvibe/skills` for namespace consistency.

8. **Internal vs browser-reachable URLs (and CORS):** the discovery env vars and the §5.3 link examples use Docker-network hostnames (`http://fpv-inventory:8000`), which the user's browser can't resolve. Client-side fetches and rendered cross-tool links need host-reachable URLs or server-side proxying. See API-CONTRACT.md §7.7. Decide before Phase 2.