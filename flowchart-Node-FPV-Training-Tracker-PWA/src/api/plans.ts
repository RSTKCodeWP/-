import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

app.get('/', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM training_plans ORDER BY created_at').all());
});

app.get('/active', (c) => {
  const db = getDb();
  const plan = db.prepare('SELECT * FROM training_plans WHERE active = 1 ORDER BY id DESC LIMIT 1').get();
  return plan ? c.json(plan) : c.json({ error: 'No active plan' }, 404);
});

app.post('/', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const isActive = body.active === true || body.active === 1 ? 1 : 0;
  const totalWeeks = parseInt(body.total_weeks) || 20;
  const result = db.transaction(() => {
    if (isActive) db.prepare('UPDATE training_plans SET active = 0').run();
    return db.prepare(
      'INSERT INTO training_plans (name, start_date, goal_date, goal_description, total_weeks, active, notes) VALUES (?, ?, ?, ?, ?, ?, ?)'
    ).run(body.name, body.start_date, body.goal_date || null, body.goal_description || null, totalWeeks, isActive, body.notes || null);
  })();
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.put('/:id', async (c) => {
  const db = getDb();
  const id = c.req.param('id');
  const body = await c.req.json();
  const isActive = body.active === true || body.active === 1 ? 1 : 0;
  const totalWeeks = parseInt(body.total_weeks) || 20;
  db.transaction(() => {
    if (isActive) db.prepare('UPDATE training_plans SET active = 0').run();
    db.prepare(
      'UPDATE training_plans SET name=?, start_date=?, goal_date=?, goal_description=?, total_weeks=?, active=?, notes=? WHERE id=?'
    ).run(body.name, body.start_date, body.goal_date || null, body.goal_description || null, totalWeeks, isActive, body.notes || null, id);
  })();
  return c.json({ ok: true });
});

export default app;
