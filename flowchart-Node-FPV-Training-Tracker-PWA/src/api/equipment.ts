import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

app.get('/', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM equipment ORDER BY platform, type, name').all());
});

app.post('/', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const result = db.prepare(`
    INSERT INTO equipment (type, name, platform, quantity_in_stock, notes)
    VALUES (?, ?, ?, ?, ?)
  `).run(body.type || 'other', body.name, body.platform || '', body.quantity_in_stock || 0, body.notes || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.put('/:id', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  db.prepare('UPDATE equipment SET type=?, name=?, platform=?, quantity_in_stock=?, notes=? WHERE id=?')
    .run(body.type, body.name, body.platform, body.quantity_in_stock, body.notes, c.req.param('id'));
  return c.json({ ok: true });
});

app.delete('/:id', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM equipment WHERE id = ?').run(c.req.param('id'));
  return c.json({ ok: true });
});

// Equipment log
app.post('/:id/log', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const result = db.prepare(`
    INSERT INTO equipment_log (equipment_id, session_id, date, action, notes)
    VALUES (?, ?, ?, ?, ?)
  `).run(c.req.param('id'), body.session_id || null, body.date || new Date().toISOString().split('T')[0], body.action || 'inspected', body.notes || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

export default app;
