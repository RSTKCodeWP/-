import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

// List all tricks
app.get('/', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM tricks ORDER BY level, name').all());
});

// List drills (before /:id so it doesn't match "drills" as an id)
app.get('/drills/all', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM drills ORDER BY id').all());
});

// List resources
app.get('/resources/all', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM resources ORDER BY type, name').all());
});

// Week schedule
app.get('/schedule/all', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM week_schedule ORDER BY week_number').all());
});

// Get single trick with recent attempt history
app.get('/:id', (c) => {
  const db = getDb();
  const id = c.req.param('id');
  const trick = db.prepare('SELECT * FROM tricks WHERE id = ?').get(id);
  if (!trick) return c.json({ error: 'Not found' }, 404);

  const history = db.prepare(`
    SELECT ta.*, s.date, s.location, s.platform
    FROM trick_attempts ta JOIN sessions s ON ta.session_id = s.id
    WHERE ta.trick_id = ?
    ORDER BY s.date DESC LIMIT 20
  `).all(id);

  return c.json({ ...(trick as any), history });
});

export default app;
