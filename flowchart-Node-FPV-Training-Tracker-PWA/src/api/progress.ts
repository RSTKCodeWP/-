import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const app = new Hono();

// Get trick mastery overview (computed from trick_attempts across all sessions)
app.get('/mastery', (c) => {
  const db = getDb();
  const mastery = db.prepare(`
    SELECT
      t.id, t.name, t.level, t.category,
      COALESCE(SUM(ta.attempts), 0) as total_attempts,
      COALESCE(SUM(ta.landed), 0) as total_landed,
      CASE WHEN SUM(ta.attempts) > 0
        THEN ROUND(100.0 * SUM(ta.landed) / SUM(ta.attempts), 1)
        ELSE NULL END as overall_rate,
      (SELECT CASE WHEN SUM(ta2.attempts) > 0
        THEN ROUND(100.0 * SUM(ta2.landed) / SUM(ta2.attempts), 1)
        ELSE NULL END
       FROM trick_attempts ta2
       JOIN sessions s2 ON ta2.session_id = s2.id
       WHERE ta2.trick_id = t.id
       AND s2.id IN (SELECT id FROM sessions ORDER BY date DESC, time_start DESC LIMIT 3)
      ) as recent_rate,
      (SELECT COUNT(DISTINCT s3.id) FROM trick_attempts ta3
       JOIN sessions s3 ON ta3.session_id = s3.id
       WHERE ta3.trick_id = t.id) as sessions_practiced
    FROM tricks t
    LEFT JOIN trick_attempts ta ON t.id = ta.trick_id
    GROUP BY t.id
    ORDER BY t.level, t.name
  `).all();
  return c.json(mastery);
});

// Get overall stats
app.get('/stats', (c) => {
  const db = getDb();

  const sessionCount = db.prepare('SELECT COUNT(*) as c FROM sessions').get() as { c: number };
  const totalPacks = db.prepare('SELECT COUNT(*) as c FROM packs').get() as { c: number };
  const totalCrashes = db.prepare('SELECT COALESCE(SUM(crashes), 0) as c FROM packs').get() as { c: number };

  // Total hours
  const hours = db.prepare(`
    SELECT COALESCE(SUM(
      CASE WHEN time_start != '' AND time_end != ''
      THEN (julianday(date || ' ' || time_end) - julianday(date || ' ' || time_start)) * 24
      ELSE 0.4 END
    ), 0) as total FROM sessions
  `).get() as { total: number };

  // Streak
  const dates = db.prepare(`SELECT DISTINCT date FROM sessions ORDER BY date DESC`).all() as { date: string }[];
  let streak = 0;
  const today = new Date().toISOString().split('T')[0];
  let checkDate = new Date(today);
  for (const row of dates) {
    const d = checkDate.toISOString().split('T')[0];
    if (row.date === d) {
      streak++;
      checkDate.setDate(checkDate.getDate() - 1);
    } else if (row.date < d) {
      break;
    }
  }

  // Sessions per week (last 8 weeks)
  const weeklySessionCounts = db.prepare(`
    SELECT strftime('%Y-W%W', date) as week, COUNT(*) as count
    FROM sessions
    GROUP BY week ORDER BY week DESC LIMIT 8
  `).all();

  // Crash patterns
  const crashPatterns = db.prepare(`
    SELECT failure_type, COUNT(*) as count FROM crashes
    GROUP BY failure_type ORDER BY count DESC
  `).all();

  return c.json({
    sessions: sessionCount.c,
    total_packs: totalPacks.c,
    total_crashes: totalCrashes.c,
    total_hours: Math.round(hours.total * 10) / 10,
    streak,
    weekly_sessions: weeklySessionCounts,
    crash_patterns: crashPatterns
  });
});

// Weekly reviews
app.get('/weekly', (c) => {
  const db = getDb();
  return c.json(db.prepare('SELECT * FROM weekly_reviews ORDER BY week_number DESC').all());
});

app.post('/weekly', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  const existing = db.prepare('SELECT id FROM weekly_reviews WHERE week_number = ?').get(body.week_number);
  if (existing) {
    db.prepare(`
      UPDATE weekly_reviews SET date_start=?, date_end=?, phase=?, sessions_real=?, sessions_sim=?,
        sessions_dvr=?, total_packs=?, total_sim_minutes=?, biggest_insight=?, pattern_noticed=?,
        next_week_priority=?, ready_to_advance=?, blocker=?
      WHERE week_number=?
    `).run(body.date_start, body.date_end, body.phase, body.sessions_real, body.sessions_sim,
      body.sessions_dvr, body.total_packs, body.total_sim_minutes, body.biggest_insight,
      body.pattern_noticed, body.next_week_priority, body.ready_to_advance ? 1 : 0, body.blocker, body.week_number);
    return c.json({ id: (existing as any).id });
  }
  const result = db.prepare(`
    INSERT INTO weekly_reviews (week_number, date_start, date_end, phase, sessions_real, sessions_sim,
      sessions_dvr, total_packs, total_sim_minutes, biggest_insight, pattern_noticed,
      next_week_priority, ready_to_advance, blocker)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(body.week_number, body.date_start, body.date_end, body.phase || '1-indoor',
    body.sessions_real || 0, body.sessions_sim || 0, body.sessions_dvr || 0,
    body.total_packs || 0, body.total_sim_minutes || 0, body.biggest_insight || '',
    body.pattern_noticed || '', body.next_week_priority || '', body.ready_to_advance ? 1 : 0, body.blocker || '');
  return c.json({ id: result.lastInsertRowid }, 201);
});

// Gate checks
app.get('/gates', (c) => {
  const db = getDb();
  const gates = db.prepare(`
    SELECT gc.*, gp.id as progress_id, gp.met, gp.date_met
    FROM gate_checks gc
    LEFT JOIN gate_progress gp ON gc.id = gp.gate_check_id
    ORDER BY gc.phase, gc.sort_order
  `).all();
  return c.json(gates);
});

app.put('/gates/:id', async (c) => {
  const db = getDb();
  const body = await c.req.json();
  db.prepare('UPDATE gate_progress SET met = ?, date_met = ? WHERE gate_check_id = ?')
    .run(body.met ? 1 : 0, body.met ? new Date().toISOString().split('T')[0] : null, c.req.param('id'));
  return c.json({ ok: true });
});

export default app;
