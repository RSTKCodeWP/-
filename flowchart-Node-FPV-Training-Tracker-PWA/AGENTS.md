# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project Overview

FPV drone freestyle training tracker - a self-hostable PWA for session logs, trick mastery, phase progression, and equipment tracking.

## Build / Dev / Test Commands

```bash
npm install        # Install dependencies
npm start          # Run server (port 3000)
npm run dev        # Run with watch mode (auto-restart on changes)
```

### Testing

No unit test framework. Tests are smoke tests via curl against a running server (see `.github/workflows/ci.yml`).

To run smoke tests manually:
```bash
node --import tsx src/server.ts &
curl -sf http://localhost:3000/api/health
curl -sf http://localhost:3000/api/tricks | jq length
```

### Environment

- `PORT` - Server port (default: 3000)
- `DB_PATH` - SQLite database path (default: `data/flowchart.db`)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Server | Hono on Node.js (TypeScript, ES modules) |
| Database | SQLite via `better-sqlite3` |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Runtime | `tsx` for TypeScript execution |

## Code Style Guidelines

### Imports

```typescript
import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { getDb } from '../db/index.js';
```

- External packages first, then local imports
- Always include `.js` extension for local imports (even for `.ts` files)
- Use named imports; avoid `import *`
- All `import` statements must come before any executable code — no initialisation between import groups

### TypeScript

- Use `const` for variables that don't change
- Prefer arrow functions: `(c) => c.json(data)`
- No explicit return types needed for simple functions
- Use type assertions when needed: `as { c: number }` or `as any` for dynamic query results
- Avoid unnecessary type complexity; keep it practical

### Naming Conventions

| Context | Convention | Example |
|---------|------------|---------|
| Variables/functions | camelCase | `currentSessionId`, `loadSessions()` |
| Database columns | snake_case | `session_id`, `pack_number`, `time_start` |
| Route files | lowercase | `sessions.ts`, `tricks.ts` |
| Constants | SCREAMING_SNAKE_CASE | `DB_PATH`, `FAILURE_TYPES` |

### API Route Pattern

Each route file exports a Hono app:

```typescript
import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

app.get('/', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM table').all());
});

app.post('/', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const result = db.prepare('INSERT INTO table (col) VALUES (?)').run(body.value);
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.put('/:id', async (c) => {
  const db = getDb();
  const id = c.req.param('id');
  const body = await c.req.json();
  db.prepare('UPDATE table SET col=? WHERE id=?').run(body.value, id);
  return c.json({ ok: true });
});

app.delete('/:id', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM table WHERE id = ?').run(c.req.param('id'));
  return c.json({ ok: true });
});

export default app;
```

### Database Access

- Use `getDb()` to get the singleton database connection
- Inline SQL queries (no ORM)
- Use prepared statements: `db.prepare('SQL').run(params)` or `.all()` or `.get()`
- For INSERT, use `result.lastInsertRowid` to return new ID

### Error Handling

Keep it simple:
- 404: `return c.json({ error: 'Not found' }, 404)`
- Success: `return c.json({ ok: true })`
- Created: `return c.json({ id: result.lastInsertRowid }, 201)`
- No try/catch needed for most handlers (let errors bubble)

### Frontend (public/)

- Vanilla JavaScript in `app.js`
- No build step, no bundler
- Use `fetch()` for API calls with the helper:
  ```javascript
  async function api(path, opts = {}) {
    const res = await fetch('/api' + path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
    return res.json();
  }
  ```
- Escape user content before rendering: `esc()` function for HTML escaping

### Comments

Avoid comments. Code should be self-explanatory through:
- Clear variable/function names
- Simple, focused functions
- Descriptive database column names

### SQL Schema

- Tables use `IF NOT EXISTS`
- Foreign keys with `ON DELETE CASCADE` where appropriate
- Default values for non-null columns
- `created_at TEXT DEFAULT (datetime('now'))` for timestamps
- SQLite booleans as INTEGER (0/1)

### Formatting

- 2-space indentation
- Single quotes for strings in JavaScript
- Template literals for SQL queries spanning multiple lines
- Blank line between route handlers

### File Structure

```
src/
  server.ts        # Main entry, route registration, static serving
  api/
    sessions.ts    # Session CRUD + packs + trick attempts + crashes + reviews
    progress.ts    # Mastery stats, weekly reviews, gate checks
    tricks.ts      # Tricks, drills, resources, schedule
    equipment.ts   # Equipment inventory
    denver.ts      # Denver trip checklist
    exportimport.ts
  db/
    index.ts       # Database singleton + init
    schema.sql     # Table definitions
    seed.sql       # Initial data (tricks, drills, gates, etc.)

public/
  index.html       # Single-page app
  app.js           # Frontend JavaScript
  style.css        # Styles
  sw.js            # Service worker
  manifest.json    # PWA manifest
```

## App Versioning

- The single source of truth for the version is `package.json`
- `server.ts` reads it at startup via `readFileSync` and exposes it through `/api/health`
- The frontend fetches `/api/health` on init and renders `v{version}` in the UI (Today tab header)
- Never hardcode the version string anywhere else — bump `package.json` and everything follows

## Pull Requests & Commits

- Do not include session URLs or agent/tool identifiers in PR bodies, commit messages, or code comments
- PR descriptions: summary bullets + a test plan checklist is enough
- Always reference the closing issue with `Resolves #X` (or `Closes #X`) in the PR body so GitHub auto-closes it on merge

## Important Notes

- The app is offline-first (PWA with service worker)
- No authentication/authorization (self-hosted, single user)
- Data is stored in SQLite file at `data/flowchart.db`
- Frontend has no build step - edit HTML/CSS/JS and refresh

## Testing Workflows

### Smoke Testing Against Running Server

Start server in background, run tests, then kill:

```bash
node --import tsx src/server.ts &
SERVER_PID=$!
sleep 2
curl -sf http://localhost:3000/api/health | jq .
# ... more tests ...
kill $SERVER_PID
```

### Common API Endpoints to Test

- `GET /api/health` - Health check
- `GET /api/tricks` - List tricks
- `POST /api/sessions` - Create session, returns `{id}`
- `POST /api/sessions/:id/tricks` - Add trick attempt (note: `landed` not `lands`)
- `POST /api/sessions/:id/packs` - Add pack with voltage/focus/crashes
- `POST /api/sessions/:id/crashes` - Log crash with failure_type
- `POST /api/sessions/:id/review` - Session review (3 good, 3 improve, fatigue, etc.)
- `GET /api/progress/gates` - Gate checks for phase progression
- `GET /api/progress/mastery` - Trick mastery stats
- `GET /api/equipment` - Equipment inventory
