# FPV Training Tracker - App Plan

A self-hostable PWA for tracking FPV freestyle training progress, session logs, trick mastery, equipment status, and the 20-week "Plan to Denver."

---

## Decision: Self-Hosted (Docker/Runtipi)

**Why not val.town first:** The data model here is relational (sessions reference tricks, crashes reference sessions, phase gates reference trick mastery levels). SQLite handles this naturally. Val.town's storage primitives (blob, sqlite) could work but would fight us on serving a PWA with service worker + manifest + offline support. The user needs to log sessions where internet may not be available (outdoor field, hotel room).

**Portability guarantee:** The server uses **Hono** (runs on Node, Deno, Bun, Cloudflare Workers, and val.town). The frontend is vanilla HTML/CSS/JS with zero build step. If you later want a val.town version, the migration path is: copy the Hono routes into a val.town HTTP val, swap SQLite calls for val.town's `sqlite` API (same SQL), and serve the static HTML from a separate val or inline it. Nothing in this design prevents that.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Server | **Hono** on Node.js | 14KB framework. Runs everywhere. No lock-in. |
| Database | **SQLite** via `better-sqlite3` | Single file, zero config, handles all the relational data. Ships inside the container. |
| Frontend | **Vanilla HTML/CSS/JS** | No React, no build step, no bundler. Single `index.html` with `<script>` tags. |
| CSS | **Pico CSS** (~10KB) or hand-rolled | Classless CSS for semantic HTML. Mobile-first. Only external dependency. Optional - can be vendored. |
| PWA | Service worker + manifest | Offline session logging, installable on home screen. |
| Container | **Docker** (single Dockerfile) | `node:20-alpine`, copies source, runs server. One port. |

### No Other Libraries

- No ORM - raw SQL via `better-sqlite3` (queries are simple enough)
- No template engine - server returns JSON, frontend renders with DOM APIs
- No state management - page-level JS with `fetch()` calls
- No build tooling - files served as-is from a `public/` directory

---

## What to Track

Derived directly from the training program PDF. Every field below maps to something explicitly described in the document.

### 1. Practice Sessions (per-session log)

```
session {
  id
  date                  -- ISO date
  time_start            -- HH:MM
  time_end              -- HH:MM
  location              -- enum: home-room-A, home-room-B, library, outdoor-field, outdoor-park, sim, custom
  platform              -- enum: Air65, Mobula6, Meteor75, Rekon3, 5-inch, sim-whoop, sim-5inch, custom
  weather               -- enum: indoor, calm, 5-8mph, 8-12mph, 12-15mph, 15+mph
  session_type          -- enum: blocked-drill, interleaved, free-flow, DVR-review, sim
  notes                 -- freetext
}
```

### 2. Packs (per-pack within a session)

```
pack {
  id
  session_id            -- FK to session
  pack_number           -- 1, 2, 3...
  voltage_start         -- e.g. 4.35
  voltage_end           -- e.g. 3.50
  focus                 -- freetext (what you drilled this pack)
  crashes               -- integer count
  notes                 -- freetext
}
```

### 3. Trick Attempts (per-session scorecard)

```
trick_attempt {
  id
  session_id            -- FK to session
  trick_id              -- FK to trick
  attempts              -- integer
  landed                -- integer
  notes                 -- freetext
}
```

(Success rate is computed: `landed / attempts`)

### 4. Crash Log

```
crash {
  id
  session_id            -- FK to session
  pack_number           -- which pack
  trick_id              -- FK to trick (nullable)
  failure_type          -- enum: orient, throttle, timing, spatial, propwash, muscle, signal, environ
  root_cause            -- enum: pilot, tune, mech, signal, environ
  action_item           -- freetext
}
```

### 5. Tricks (reference database, pre-seeded)

```
trick {
  id
  name                  -- e.g. "Power Loop"
  level                 -- 1-5 (from the PDF's trick level system)
  category              -- enum: roll, flip-loop, yaw-spin, combo, recovery
  description           -- short technique summary
  indoor_notes          -- indoor-specific technique (e.g. throttle blip method)
  reference_links       -- JSON array of {label, url} (YouTube channels, Pro Whooper pages, etc.)
  prerequisites         -- JSON array of trick IDs
  phase_introduced      -- which phase (1-4) this trick is first trained
}
```

Pre-seeded from the PDF:

**Level 1:** Clean Roll (L), Clean Roll (R), Clean Flip (fwd), Clean Flip (back), Yaw Spin, Gap Threading, Coordinated Turn

**Level 2:** Split-S, Power Loop (indoor), Power Loop (outdoor), Matty Flip, Immelmann Turn

**Level 3:** Trippy Spin, Inverted Yaw Spin, Rubik's Cube, Juicy Flick

**Level 4:** Stall Rewind (advanced), Powerloop-Dive Combo

**Level 5 (aspirational):** Hamhook, Rodeo 7, McTwist, Sbang, Kururi

**Cross-level:** Stall Flip Rewind, Side Rewind, Stall Rewind w/ Yaw

### 6. Drills (reference database, pre-seeded)

```
drill {
  id
  name                  -- e.g. "Double-Door Figure-8 Flow Drill"
  description           -- from the PDF's drill library
  mastery_criteria      -- what "done" looks like
  related_tricks        -- JSON array of trick IDs this drill builds toward
  space_required        -- enum: indoor-small, indoor-large, outdoor-open, outdoor-proximity
}
```

Pre-seeded: Figure-8 Flow, Orbit, Punch-Out-and-Catch, Ceiling Scrape, Inverted Hang, Doorway Gap Threading, Wall Proximity, IGOW Line Pressure.

### 7. Post-Session Review

```
review {
  id
  session_id            -- FK to session (1:1)
  good_1                -- freetext
  good_2                -- freetext
  good_3                -- freetext
  improve_1             -- freetext
  improve_2             -- freetext
  improve_3             -- freetext
  fatigue               -- enum: fresh, good, tired, sloppy
  frustration           -- enum: none, mild, moderate, high
  stopped_before_bad    -- boolean (did I stop before encoding bad habits?)
  tomorrow_focus        -- freetext
  sim_drill_tonight     -- freetext
  dvr_timestamps        -- freetext
  blackbox_recorded     -- boolean
}
```

### 8. Weekly Review

```
weekly_review {
  id
  week_number           -- 1-20
  date_start            -- ISO date
  date_end              -- ISO date
  phase                 -- enum: 1-indoor, 2-outdoor, 3-flow, 4-denver
  sessions_real         -- integer
  sessions_sim          -- integer
  sessions_dvr          -- integer
  total_packs           -- integer
  total_sim_minutes     -- integer
  biggest_insight       -- freetext
  pattern_noticed       -- freetext
  next_week_priority    -- freetext
  ready_to_advance      -- boolean
  blocker               -- freetext (if not ready)
}
```

### 9. Trick Mastery Snapshots (per-trick per-week)

```
mastery_snapshot {
  id
  weekly_review_id      -- FK
  trick_id              -- FK
  success_rate          -- percentage (nullable for timed tricks)
  hold_time_seconds     -- for inverted hang, ceiling scrape (nullable)
  clean_laps            -- for orbits, figure-8 (nullable)
  variance_seconds      -- for figure-8 consistency (nullable)
  status                -- enum: not-started, learning (<50%), reliable (70-89%), mastered (90%+)
  trend                 -- enum: up, down, flat
  notes                 -- freetext
}
```

### 10. Phase Gate Checks

```
gate_check {
  id
  phase                 -- 1, 2, 3, or 4
  item_text             -- the gate requirement text (pre-seeded from PDF)
  is_hard_gate          -- boolean (bold items in PDF are hard gates)
  sort_order            -- display order
}

gate_progress {
  id
  gate_check_id         -- FK
  weekly_review_id      -- FK (when it was checked)
  met                   -- boolean
  date_met              -- ISO date (nullable)
}
```

Pre-seeded gate items from the PDF:

**Phase 1 -> 2:** Clean rolls/flips 70%+ both directions, Inverted hover 5+ sec / <1ft drift, Split-S indoors 3/5, Power loop indoors 3/5, Figure-8 variance <2s, Thread <3ft gaps consistently, Ceiling scrape 10s, 15+ hours combined time.

**Phase 2 -> 3:** 5+ outdoor 5-inch packs no uncontrolled crashes, Clean rolls/flips/split-S at altitude, Orientation maintained after tricks, 8-10mph wind confident, Proximity within 10ft, Smooth landings, One power loop landed.

**Phase 3 -> 4:** 3-trick combo smooth 3/5, Adapt to new location in 2-3 packs, 5+ trick repertoire at 70%+, DVR reviewed every session, 10-15mph wind comfortable, 3+ locations.

**Phase 4 (Final Exam):** 45-sec continuous line (flow + vertical + technical + recovery), No ground touches, Smooth throttle, Locations scouted, Spares packed.

### 11. Equipment Inventory

```
equipment {
  id
  type                  -- enum: frame, prop, canopy, motor, battery, camera, fc, esc, vtx, rx, other
  name                  -- e.g. "BetaFPV Meteor65 frame"
  platform              -- which quad it's for
  quantity_in_stock     -- integer
  notes                 -- freetext
}

equipment_log {
  id
  equipment_id          -- FK
  session_id            -- FK (nullable)
  date                  -- ISO date
  action                -- enum: replaced, damaged, ordered, received, inspected
  notes                 -- freetext
}
```

### 12. Denver Trip Prep (dedicated checklist)

```
denver_item {
  id
  category              -- enum: locations, legal, equipment, logistics
  text                  -- item description
  completed             -- boolean
  notes                 -- freetext
  sort_order
}
```

Pre-seeded:
- **Locations:** Scout Chatfield State Park model airfield, Find private property options, Check areas outside city park jurisdiction, Identify hotel whoop-friendly rooms
- **Legal:** TRUST test completion proof, FAA registration for >250g, B4UFLY app installed, Check LAANC for DEN Class B, Check Centennial Airport (APA) Class D
- **Equipment:** Pack spare frames, Pack spare props (20+), Pack spare batteries, Pack spare motors, BT2.0 pigtails, Test ELRS link in RF-noisy environment, Verify DJI O4 video in urban RF
- **Logistics:** Spotter arranged, Battery charging solution for travel, Toolkit packed

---

## UI Screens

The app is a single-page app with tab-based navigation. Mobile-first. Each "screen" is a section that swaps via JS. No router library needed - just show/hide with `hidden` attribute or a thin `data-page` system.

### Bottom Nav (5 tabs)

```
[Today] [Sessions] [Progress] [Tricks] [Denver]
```

### 1. Today (home screen)

- Current week number (e.g. "Week 4 of 20") and phase name
- This week's primary drills (from the PDF schedule, stored as seed data)
- Quick-start button: "Log Session" (opens session form)
- Active session card (if one is in progress)
- Streak counter: consecutive days with a session
- Next go/no-go gates to hit (from phase gate checks, showing unmet items)

### 2. Sessions

- **List view:** Scrollable list of past sessions, most recent first. Shows date, location, platform, pack count, crash count.
- **Session detail:** Full session log, packs, trick scorecard, crash log, post-session review. All editable.
- **New session form:** Step-through flow:
  1. Header (date/time/location/platform/weather/type) - auto-fills date and time
  2. Packs (add packs one at a time, minimal fields)
  3. Trick scorecard (tap tricks from your active list, enter attempts/landed)
  4. Crash log (optional, add crashes with taxonomy dropdowns)
  5. Post-session review (3 good / 3 improve / fatigue / frustration)

The form should save as you go (not require a final "submit") so data isn't lost if you close the app mid-session.

### 3. Progress

- **Phase overview:** Visual progress bar showing Phase 1-4, current position, and gate completion percentage for current phase.
- **Trick mastery table:** All tricks with current status (learning/reliable/mastered), success rate from last 3 sessions, trend arrows. Tap a trick to see its history chart.
- **Weekly review form:** Fill out the weekly review. Shows auto-calculated totals (session count, pack count) from that week's session data.
- **Stats dashboard:**
  - Total hours (real + sim)
  - Sessions per week (bar chart - simple canvas, no charting library)
  - Trick mastery over time (sparklines per trick)
  - Most common crash types (from crash taxonomy data)

### 4. Tricks (reference + links)

- **Trick list:** Grouped by level (1-5). Each shows name, status badge, and success rate.
- **Trick detail:** Description, indoor notes, technique tips, prerequisites (linked), and **reference links** (tappable links to YouTube channels and resources from the PDF).
- **Drill library:** All drills with descriptions and mastery criteria.
- **Reference hub:** Organized links to all resources mentioned in the PDF:
  - YouTube: Headmazta, Infinity Loops, Joshua Bardwell, Mr. Steele, Skitzo, Le Drib, GAPiT FPV, Astrorocketz
  - Sites: Pro Whooper (prowhooper.com), Oscar Liang (oscarliang.com), FPV Mastery, FPV Unlocked, GetFPV Learn
  - Communities: IntoFPV, r/fpv, r/TinyWhoop, MultiGP, VelociDrone Discord
  - Tools: B4UFLY app, AirMap, Blackbox Explorer, PIDtoolbox, UAV Forecast
  - Sims: VelociDrone, Liftoff: Micro Drones, TRYP FPV

### 5. Denver

- **Week timeline:** Visual 20-week timeline showing current position, phase boundaries, and completed/upcoming milestones.
- **Phase gate checklist:** Interactive checklist for current phase gates. Hard gates highlighted. Check items off as met.
- **Denver prep checklist:** The locations/legal/equipment/logistics checklist with completion tracking.
- **Countdown:** Days until July 2026.

---

## Data Import/Export

### Export Format

Single JSON file containing the entire database:

```json
{
  "export_version": 1,
  "exported_at": "2026-02-08T12:00:00Z",
  "app_version": "1.0.0",
  "sessions": [...],
  "packs": [...],
  "trick_attempts": [...],
  "crashes": [...],
  "reviews": [...],
  "weekly_reviews": [...],
  "mastery_snapshots": [...],
  "gate_progress": [...],
  "equipment": [...],
  "equipment_log": [...],
  "denver_items": [...],
  "custom_tricks": [...],
  "custom_drills": [...]
}
```

Pre-seeded reference data (tricks, drills, gate checks) is NOT included in exports - it ships with the app. Only user-created data and user-added custom entries export.

### Import

- Upload JSON file via the UI
- Validates schema version
- Merge strategy: import only adds data, never overwrites. Duplicate detection by `(date, time_start, location)` for sessions.
- Confirmation dialog showing what will be imported before committing.

### API Endpoints

```
GET  /api/export          -- returns full JSON export
POST /api/import          -- accepts JSON, returns merge preview, then confirm
```

The export button should also work offline via the service worker (generate JSON client-side from cached data).

---

## PWA Strategy

### Manifest (`manifest.json`)

```json
{
  "name": "FPV Training Tracker",
  "short_name": "FPV Tracker",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#e94560",
  "icons": [...]
}
```

### Service Worker

- **Cache-first** for all static assets (HTML, CSS, JS, icons)
- **Network-first** for API calls, falling back to cached responses
- **Background sync** for session data: if offline, queue API writes in IndexedDB and sync when connectivity returns
- This means you can log a full session at an outdoor field with no signal and it syncs when you get home

### Offline Capability

The session logging form must work fully offline:
1. Service worker caches the app shell
2. Trick list and drill data are cached on first load
3. New session data writes to IndexedDB immediately
4. Background sync pushes to server when online
5. Export can be generated client-side from IndexedDB

---

## Project Structure

```
fpv-tracker/
  Dockerfile
  docker-compose.yml
  package.json
  src/
    server.ts             -- Hono app, API routes, serves static files
    db/
      schema.sql          -- CREATE TABLE statements
      seed.sql            -- Pre-seeded tricks, drills, gate checks, denver items
      migrations/         -- Numbered migration files for schema changes
    api/
      sessions.ts         -- CRUD for sessions, packs, trick attempts, crashes
      reviews.ts          -- Post-session and weekly reviews
      progress.ts         -- Mastery snapshots, gate progress
      equipment.ts        -- Equipment inventory and log
      denver.ts           -- Denver prep checklist
      export.ts           -- Import/export handlers
  public/
    index.html            -- Single HTML file, all UI
    style.css             -- All styles, mobile-first
    app.js                -- All client-side JS
    sw.js                 -- Service worker
    manifest.json         -- PWA manifest
    icons/                -- App icons (generated, multiple sizes)
  data/                   -- SQLite database file lives here (Docker volume mount)
```

Total file count: ~15 source files. No build step. `node src/server.ts` (or `tsx src/server.ts`) starts the app.

---

## Runtipi Breadcrumbs

Runtipi app store apps live in a repo with this structure:

```
apps/
  fpv-tracker/
    config.json           -- App metadata (name, description, port, etc.)
    docker-compose.yml    -- How to run the container
    metadata/
      description.md      -- Long description for the app store
      logo.jpg            -- App icon
```

### What the `config.json` needs:

```json
{
  "id": "fpv-tracker",
  "name": "FPV Training Tracker",
  "description": "Track FPV freestyle training progress, trick mastery, and session logs",
  "port": 3000,
  "available": true,
  "categories": ["utilities"],
  "version": "1.0.0",
  "tipiVersion": 1,
  "source": "https://github.com/<your-user>/fpv-tracker",
  "website": "",
  "exposable": true,
  "no_auth": false,
  "form_fields": []
}
```

### What the `docker-compose.yml` needs:

```yaml
version: "3.7"
services:
  fpv-tracker:
    image: ghcr.io/<your-user>/fpv-tracker:latest
    container_name: fpv-tracker
    restart: unless-stopped
    ports:
      - "${APP_PORT:-3000}:3000"
    volumes:
      - ${APP_DATA_DIR}/data:/app/data
    environment:
      - NODE_ENV=production
```

### Key decisions for Runtipi compatibility:

1. **Single container.** No separate database container - SQLite lives inside the app container with a volume mount for persistence.
2. **Single port.** Runtipi proxies traffic to one port. The Hono server serves both API and static files on port 3000.
3. **Data directory.** SQLite file at `/app/data/fpv-tracker.db`. Runtipi mounts `${APP_DATA_DIR}/data` to this path, so backups are just copying a single file.
4. **No environment variables required.** App works out of the box with zero config. Optional env vars for things like backup schedule could be added later.

### Dockerfile sketch:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production
COPY src/ src/
COPY public/ public/
RUN mkdir -p /app/data
EXPOSE 3000
CMD ["node", "--import", "tsx", "src/server.ts"]
```

---

## Reference Links Integration

The PDF references specific YouTube channels and websites for each trick and phase. These are stored in the `trick.reference_links` JSON field and in a separate `resources` seed table:

```
resource {
  id
  name                  -- e.g. "Headmazta"
  type                  -- enum: youtube, website, app, community, sim, tool
  url                   -- channel or site URL
  description           -- what it's useful for
  tricks_covered        -- JSON array of trick names/IDs
}
```

Pre-seeded resources from the PDF:

| Resource | Type | URL Pattern | Used For |
|----------|------|-------------|----------|
| Headmazta | youtube | youtube.com/@headmazta | Rolls, inverted, orbits, power loops (NTTT series) |
| Infinity Loops | youtube | youtube.com/@infinityloops | Split-S, power loops, trippy spins (Whooptorial Wednesday) |
| Pro Whooper | website | prowhooper.com | Tricktionary, Freestyle Boot Camp, IGOW, split-S, matty flip, rewind, trippy spin |
| Joshua Bardwell | youtube | youtube.com/@joshuabardwell | First outdoor flights, maiden checklist, Betaflight config |
| Oscar Liang | website | oscarliang.com | PID tuning, Blackbox analysis, propwash |
| Mr. Steele | youtube | youtube.com/@mrsteele | Proximity philosophy |
| Skitzo | youtube | youtube.com/@skitzo | Flow |
| Le Drib | youtube | youtube.com/@ledrib | Freestyle lines |
| GAPiT FPV | youtube | youtube.com/@gapitfpv | Pauses and backtracking |
| Astrorocketz | youtube | youtube.com/@astrorocketz | Matty flip progression |
| FPVFrenzy | website | fpvfrenzy.com | "Lessons in Flow" article |
| GetFPV | website | getfpv.com/learn | Psychology at events, general education |
| B4UFLY | app | faa.gov/uas/getting_started/b4ufly | Airspace checking |
| AirMap | app/website | airmap.com | Airspace/LAANC |
| TRYP FPV | sim | Steam | 5-inch freestyle sim environments |
| Blackbox Explorer | tool | web-based | Quick Blackbox log viewing |
| PIDtoolbox | tool | github.com/bw1129/PIDtoolbox | Deep Blackbox analysis |

In the Tricks screen, each trick card shows clickable reference links. The "Reference Hub" tab collects all resources in one searchable list.

---

## Implementation Order

Build in this order so each step produces a usable (if incomplete) app:

### Step 1: Server skeleton + database + seed data
- Hono server serving static files
- SQLite schema creation on startup
- Seed data: all tricks, drills, phase gates, Denver checklist, resources
- Single API health check endpoint

### Step 2: Session logging (core loop)
- New session form (header + packs + trick scorecard)
- Session list view
- Session detail view
- This is the feature used daily, so it ships first

### Step 3: Post-session review
- Review form attached to sessions
- "3 good / 3 improve" UI
- Fatigue/frustration tracking

### Step 4: Crash logging
- Crash form with taxonomy dropdowns
- Crash list within session detail
- Pattern detection: highlight when same failure_type appears 3+ times

### Step 5: Tricks + reference links
- Trick list grouped by level
- Trick detail with description, indoor notes, reference links
- Drill library
- Reference hub page

### Step 6: Progress tracking
- Trick mastery table (computed from trick_attempt data across sessions)
- Weekly review form with auto-calculated totals
- Mastery snapshots (point-in-time records for trend tracking)

### Step 7: Denver / Phase tracker
- 20-week timeline visualization
- Phase gate checklist (interactive)
- Denver prep checklist
- Countdown

### Step 8: PWA + offline
- Service worker
- Manifest
- IndexedDB offline queue
- Background sync

### Step 9: Import/export
- JSON export of all user data
- JSON import with merge logic
- Export button in UI (works offline too)

### Step 10: Docker + Runtipi prep
- Dockerfile
- docker-compose.yml
- Document the runtipi app store config structure (don't write it here - that goes in the app store repo)
- Test: `docker compose up` runs the full app

---

## Design Notes

### Mobile-first CSS approach

- Base styles target 320px+ (phone in portrait)
- Session form uses full-width stacked inputs
- Trick scorecard uses a compact row layout: `[trick name] [attempts] [landed]` as tappable number inputs
- Bottom nav is fixed position with 5 equal-width tabs
- Dark theme default (FPV pilots are used to dark UIs from Betaflight/goggles)
- High contrast for outdoor readability

### Session form UX priorities

The session form is used immediately after flying, often standing in a field. Design for:
- **Large tap targets** (48px minimum)
- **Auto-fill defaults** from last session (same location, same platform)
- **Quick trick entry**: show only tricks you've been working on recently, not the full 25+ trick database. "Add trick" button to pull from the full list.
- **Save continuously** - every field change persists immediately. No "submit" button to lose to a pocket touch.
- **Pack entry is minimal**: voltage start/end and focus text. Crash count is a +/- stepper.

### Computed metrics (no manual entry needed)

These are calculated from raw data, never stored:
- Trick success rate (per-session and rolling average)
- Sessions per week
- Total hours (sum of session durations)
- Streak (consecutive days with at least one session)
- Phase gate completion percentage
- Most common crash failure types
- Equipment replacement intervals

---

## Val.town Migration Path (for future reference)

If you later want to run this on val.town:

1. **Server**: Copy `src/server.ts` and `src/api/*.ts` into a single HTTP val. Hono works on val.town natively (`import { Hono } from "npm:hono"`).
2. **Database**: Replace `better-sqlite3` calls with val.town's `sqlite` API. The SQL is identical - just the driver changes.
3. **Frontend**: Either serve from a separate val using `export default function(req)` returning HTML, or host the static files elsewhere and CORS the API.
4. **PWA**: Service worker registration requires the HTML to be served from the same origin as the API. Val.town can do this if both are in the same val.
5. **Offline**: IndexedDB + background sync work the same regardless of hosting.

The main friction point is that val.town's sqlite doesn't support `better-sqlite3`'s synchronous API - you'd change to async calls. This is a find-and-replace level change, not an architectural one.
