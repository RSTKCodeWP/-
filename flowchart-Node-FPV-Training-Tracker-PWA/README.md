# flowchart

A self-hostable PWA for tracking FPV freestyle training progress, session logs, trick mastery, and the 20-week "Plan to Denver."

## Quick Start

```bash
npm install
npm start          # http://localhost:3000
```

For development with auto-restart:

```bash
npm run dev
```

## Environment

- `PORT` - Server port (default: 3000)
- `DB_PATH` - SQLite database path (default: `data/fpv-tracker.db`)

## Features

- **Session logging** - Track practice sessions with packs, trick attempts, crashes, and post-session reviews
- **Trick mastery** - Monitor progress across 5 skill levels with computed success rates
- **Phase progression** - 20-week training program with gate checks
- **Denver countdown** - Prep checklist for the July 2026 trip
- **Offline-capable** - PWA with service worker (see known limitations below)
- **Self-hosted** - Single SQLite file, Docker-ready

## Tech Stack

| Layer | Technology |
|-------|------------|
| Server | Hono on Node.js (TypeScript) |
| Database | SQLite via `better-sqlite3` |
| Frontend | Vanilla HTML/CSS/JS (no build step) |

## API Endpoints

| Route | Description |
|-------|-------------|
| `GET /api/health` | Health check |
| `GET/POST /api/sessions` | Session list / create |
| `GET/PUT/DELETE /api/sessions/:id` | Session CRUD |
| `POST /api/sessions/:id/packs` | Add pack to session |
| `POST /api/sessions/:id/tricks` | Log trick attempt |
| `POST /api/sessions/:id/crashes` | Log crash |
| `POST /api/sessions/:id/review` | Save session review |
| `GET /api/progress/stats` | Overall statistics |
| `GET /api/progress/mastery` | Trick mastery overview |
| `GET /api/progress/gates` | Phase gate checks |
| `GET /api/tricks` | All tricks |
| `GET /api/tricks/drills/all` | Drill list |
| `GET /api/tricks/resources/all` | Learning resources |
| `GET /api/tricks/schedule/all` | 20-week schedule |
| `GET /api/data/export` | Export all data as JSON |
| `POST /api/data/import` | Import data from JSON |

## Docker

```bash
docker build -t flowchart .
docker run -p 3000:3000 -v ./data:/app/data flowchart
```

Or with docker-compose:

```bash
docker-compose up -d
```

## Known Issues

See [ISSUE-offline-first.md](./ISSUE-offline-first.md) - write operations require server connectivity. Full offline support with IndexedDB sync queue is planned.

## License

MIT
