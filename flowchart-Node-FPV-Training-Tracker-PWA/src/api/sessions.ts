import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

// List sessions
app.get('/', (c) => {
  const db = getDb();
  const sessions = db.prepare(`
    SELECT s.*,
      (SELECT COUNT(*) FROM packs WHERE session_id = s.id) as pack_count,
      (SELECT COALESCE(SUM(crashes), 0) FROM packs WHERE session_id = s.id) as crash_count
    FROM sessions s ORDER BY s.date DESC, s.time_start DESC
  `).all();
  return c.json(sessions);
});

// Get single session with all related data
app.get('/:id', (c) => {
  const db = getDb();
  const id = c.req.param('id');
  const session = db.prepare('SELECT * FROM sessions WHERE id = ?').get(id);
  if (!session) return c.json({ error: 'Not found' }, 404);

  const packs = db.prepare('SELECT * FROM packs WHERE session_id = ? ORDER BY pack_number').all(id);
  const trick_attempts = db.prepare(`
    SELECT ta.*, t.name as trick_name, t.level as trick_level
    FROM trick_attempts ta JOIN tricks t ON ta.trick_id = t.id
    WHERE ta.session_id = ?
  `).all(id);
  const crashes = db.prepare(`
    SELECT cr.*, t.name as trick_name
    FROM crashes cr LEFT JOIN tricks t ON cr.trick_id = t.id
    WHERE cr.session_id = ?
  `).all(id);
  const review = db.prepare('SELECT * FROM reviews WHERE session_id = ?').get(id);

  return c.json({ ...session as any, packs, trick_attempts, crashes, review });
});

// Create session
app.post('/', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const stmt = db.prepare(`
    INSERT INTO sessions (date, time_start, time_end, location, platform, weather, session_type, notes, training_plan_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  const result = stmt.run(
    body.date || new Date().toISOString().split('T')[0],
    body.time_start || new Date().toTimeString().slice(0, 5),
    body.time_end || '',
    body.location || 'home-room-A',
    body.platform || 'Air65',
    body.weather || 'indoor',
    body.session_type || 'blocked-drill',
    body.notes || '',
    body.training_plan_id || null
  );
  return c.json({ id: result.lastInsertRowid }, 201);
});

// Update session
app.put('/:id', async (c) => {
  const db = getDb();
  const id = c.req.param('id');
  const body = await c.req.json();
  db.prepare(`
    UPDATE sessions SET date=?, time_start=?, time_end=?, location=?, platform=?, weather=?, session_type=?, notes=?, training_plan_id=?
    WHERE id=?
  `).run(body.date, body.time_start, body.time_end, body.location, body.platform, body.weather, body.session_type, body.notes, body.training_plan_id || null, id);
  return c.json({ ok: true });
});

// Delete session
app.delete('/:id', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM sessions WHERE id = ?').run(c.req.param('id'));
  return c.json({ ok: true });
});

// --- Packs ---
app.post('/:id/packs', async (c) => {
  const db = getDb();
  const sessionId = c.req.param('id');
  const body = await c.req.json();
  const maxPack = db.prepare('SELECT COALESCE(MAX(pack_number), 0) as m FROM packs WHERE session_id = ?').get(sessionId) as { m: number };
  const result = db.prepare(`
    INSERT INTO packs (session_id, pack_number, voltage_start, voltage_end, focus, crashes, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(sessionId, (maxPack.m || 0) + 1, body.voltage_start, body.voltage_end, body.focus || '', body.crashes || 0, body.notes || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.put('/:sid/packs/:pid', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  db.prepare(`
    UPDATE packs SET voltage_start=?, voltage_end=?, focus=?, crashes=?, notes=? WHERE id=?
  `).run(body.voltage_start, body.voltage_end, body.focus, body.crashes, body.notes, c.req.param('pid'));
  return c.json({ ok: true });
});

app.delete('/:sid/packs/:pid', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM packs WHERE id = ?').run(c.req.param('pid'));
  return c.json({ ok: true });
});

// --- Trick Attempts ---
app.post('/:id/tricks', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const result = db.prepare(`
    INSERT INTO trick_attempts (session_id, trick_id, attempts, landed, notes)
    VALUES (?, ?, ?, ?, ?)
  `).run(c.req.param('id'), body.trick_id, body.attempts || 0, body.landed || 0, body.notes || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.put('/:sid/tricks/:tid', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  // Only update trick_id if provided and non-zero, otherwise keep existing
  if (body.trick_id) {
    db.prepare('UPDATE trick_attempts SET trick_id=?, attempts=?, landed=?, notes=? WHERE id=?')
      .run(body.trick_id, body.attempts, body.landed, body.notes || '', c.req.param('tid'));
  } else {
    db.prepare('UPDATE trick_attempts SET attempts=?, landed=?, notes=? WHERE id=?')
      .run(body.attempts, body.landed, body.notes || '', c.req.param('tid'));
  }
  return c.json({ ok: true });
});

app.delete('/:sid/tricks/:tid', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM trick_attempts WHERE id = ?').run(c.req.param('tid'));
  return c.json({ ok: true });
});

// --- Crashes ---
app.post('/:id/crashes', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const result = db.prepare(`
    INSERT INTO crashes (session_id, pack_number, trick_id, failure_type, root_cause, action_item)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(c.req.param('id'), body.pack_number, body.trick_id || null, body.failure_type || 'orient', body.root_cause || 'pilot', body.action_item || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

app.delete('/:sid/crashes/:cid', (c) => {
  const db = getDb();
  db.prepare('DELETE FROM crashes WHERE id = ?').run(c.req.param('cid'));
  return c.json({ ok: true });
});

// --- Reviews ---
app.post('/:id/review', async (c) => {
  const db = getDb();
  const sessionId = c.req.param('id');
  const body = await c.req.json();
  // Upsert
  const existing = db.prepare('SELECT id FROM reviews WHERE session_id = ?').get(sessionId);
  if (existing) {
    db.prepare(`
      UPDATE reviews SET good_1=?, good_2=?, good_3=?, improve_1=?, improve_2=?, improve_3=?,
        fatigue=?, frustration=?, stopped_before_bad=?, tomorrow_focus=?, sim_drill_tonight=?,
        dvr_timestamps=?, blackbox_recorded=?
      WHERE session_id=?
    `).run(body.good_1, body.good_2, body.good_3, body.improve_1, body.improve_2, body.improve_3,
      body.fatigue, body.frustration, body.stopped_before_bad ? 1 : 0, body.tomorrow_focus,
      body.sim_drill_tonight, body.dvr_timestamps, body.blackbox_recorded ? 1 : 0, sessionId);
  } else {
    db.prepare(`
      INSERT INTO reviews (session_id, good_1, good_2, good_3, improve_1, improve_2, improve_3,
        fatigue, frustration, stopped_before_bad, tomorrow_focus, sim_drill_tonight, dvr_timestamps, blackbox_recorded)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(sessionId, body.good_1 || '', body.good_2 || '', body.good_3 || '', body.improve_1 || '', body.improve_2 || '', body.improve_3 || '',
      body.fatigue || 'good', body.frustration || 'none', body.stopped_before_bad ? 1 : 0,
      body.tomorrow_focus || '', body.sim_drill_tonight || '', body.dvr_timestamps || '', body.blackbox_recorded ? 1 : 0);
  }
  return c.json({ ok: true });
});

export default app;
