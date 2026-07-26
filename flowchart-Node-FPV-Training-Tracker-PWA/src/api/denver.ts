import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

app.get('/', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM denver_items ORDER BY category, sort_order').all());
});

app.put('/:id', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  db.prepare('UPDATE denver_items SET completed=?, notes=? WHERE id=?')
    .run(body.completed ? 1 : 0, body.notes || '', c.req.param('id'));
  return c.json({ ok: true });
});

export default app;
