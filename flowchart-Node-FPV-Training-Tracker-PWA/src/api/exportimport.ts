import { readFileSync } from 'node:fs';
import { Hono } from 'hono';
import { getDb } from '../db/index.js';

const { version: APP_VERSION } = JSON.parse(
  readFileSync(new URL('../../package.json', import.meta.url), 'utf-8')
);

const app = new Hono();

app.get('/export', (c) => {
  const db = getDb();
  const data = {
    export_version: 1,
    exported_at: new Date().toISOString(),
    app_version: APP_VERSION,
    sessions: db.prepare('SELECT * FROM sessions').all(),
    packs: db.prepare('SELECT * FROM packs').all(),
    trick_attempts: db.prepare('SELECT * FROM trick_attempts').all(),
    crashes: db.prepare('SELECT * FROM crashes').all(),
    reviews: db.prepare('SELECT * FROM reviews').all(),
    weekly_reviews: db.prepare('SELECT * FROM weekly_reviews').all(),
    mastery_snapshots: db.prepare('SELECT * FROM mastery_snapshots').all(),
    gate_progress: db.prepare('SELECT * FROM gate_progress').all(),
    equipment: db.prepare('SELECT * FROM equipment').all(),
    equipment_log: db.prepare('SELECT * FROM equipment_log').all(),
    denver_items: db.prepare("SELECT * FROM denver_items WHERE completed = 1 OR notes != ''").all(),
  };
  c.header('Content-Disposition', `attachment; filename="fpv-tracker-export-${new Date().toISOString().split('T')[0]}.json"`);
  return c.json(data);
});

app.post('/import', async (c) => {
  const db = getDb();
  const data = await c.req.json();

  if (!data.export_version) {
    return c.json({ error: 'Invalid export file - missing export_version' }, 400);
  }

  const stats = { sessions: 0, packs: 0, trick_attempts: 0, crashes: 0, reviews: 0 };

  const importTx = db.transaction(() => {
    // Import sessions (skip duplicates by date+time_start+location)
    if (data.sessions) {
      const insert = db.prepare(`
        INSERT INTO sessions (date, time_start, time_end, location, platform, weather, session_type, notes)
        SELECT ?, ?, ?, ?, ?, ?, ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM sessions WHERE date=? AND time_start=? AND location=?)
      `);
      const idMap = new Map<number, number>();

      for (const s of data.sessions) {
        const result = insert.run(s.date, s.time_start, s.time_end, s.location, s.platform, s.weather,
          s.session_type, s.notes, s.date, s.time_start, s.location);
        if (result.changes > 0) {
          idMap.set(s.id, Number(result.lastInsertRowid));
          stats.sessions++;
        }
      }

      // Import packs for new sessions
      if (data.packs) {
        const insertPack = db.prepare(`
          INSERT INTO packs (session_id, pack_number, voltage_start, voltage_end, focus, crashes, notes)
          VALUES (?, ?, ?, ?, ?, ?, ?)
        `);
        for (const p of data.packs) {
          const newSessionId = idMap.get(p.session_id);
          if (newSessionId) {
            insertPack.run(newSessionId, p.pack_number, p.voltage_start, p.voltage_end, p.focus, p.crashes, p.notes);
            stats.packs++;
          }
        }
      }

      // Import trick attempts for new sessions
      if (data.trick_attempts) {
        const insertTa = db.prepare(`
          INSERT INTO trick_attempts (session_id, trick_id, attempts, landed, notes) VALUES (?, ?, ?, ?, ?)
        `);
        for (const ta of data.trick_attempts) {
          const newSessionId = idMap.get(ta.session_id);
          if (newSessionId) {
            insertTa.run(newSessionId, ta.trick_id, ta.attempts, ta.landed, ta.notes);
            stats.trick_attempts++;
          }
        }
      }

      // Import crashes for new sessions
      if (data.crashes) {
        const insertCr = db.prepare(`
          INSERT INTO crashes (session_id, pack_number, trick_id, failure_type, root_cause, action_item)
          VALUES (?, ?, ?, ?, ?, ?)
        `);
        for (const cr of data.crashes) {
          const newSessionId = idMap.get(cr.session_id);
          if (newSessionId) {
            insertCr.run(newSessionId, cr.pack_number, cr.trick_id, cr.failure_type, cr.root_cause, cr.action_item);
            stats.crashes++;
          }
        }
      }

      // Import reviews for new sessions
      if (data.reviews) {
        const insertRev = db.prepare(`
          INSERT INTO reviews (session_id, good_1, good_2, good_3, improve_1, improve_2, improve_3,
            fatigue, frustration, stopped_before_bad, tomorrow_focus, sim_drill_tonight, dvr_timestamps, blackbox_recorded)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);
        for (const r of data.reviews) {
          const newSessionId = idMap.get(r.session_id);
          if (newSessionId) {
            insertRev.run(newSessionId, r.good_1, r.good_2, r.good_3, r.improve_1, r.improve_2, r.improve_3,
              r.fatigue, r.frustration, r.stopped_before_bad, r.tomorrow_focus, r.sim_drill_tonight, r.dvr_timestamps, r.blackbox_recorded);
            stats.reviews++;
          }
        }
      }
    }

    // Import gate progress
    if (data.gate_progress) {
      for (const gp of data.gate_progress) {
        if (gp.met) {
          db.prepare('UPDATE gate_progress SET met = 1, date_met = ? WHERE gate_check_id = ? AND met = 0')
            .run(gp.date_met, gp.gate_check_id);
        }
      }
    }
  });

  importTx();
  return c.json({ ok: true, imported: stats });
});

export default app;
