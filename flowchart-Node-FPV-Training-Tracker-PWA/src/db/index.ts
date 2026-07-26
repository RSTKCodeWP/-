import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const DB_PATH = process.env.DB_PATH || join(__dirname, '..', '..', 'data', 'flowchart.db');

let db: Database.Database;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initDb(db);
  }
  return db;
}

function initDb(db: Database.Database) {
  const schema = readFileSync(join(__dirname, 'schema.sql'), 'utf-8');
  db.exec(schema);

  const sessionCols = (db.pragma('table_info(sessions)') as { name: string }[]).map(c => c.name);
  if (!sessionCols.includes('training_plan_id')) {
    db.exec('ALTER TABLE sessions ADD COLUMN training_plan_id INTEGER REFERENCES training_plans(id)');
  }

  const count = db.prepare('SELECT COUNT(*) as c FROM tricks').get() as { c: number };
  if (count.c === 0) {
    const seed = readFileSync(join(__dirname, 'seed.sql'), 'utf-8');
    db.exec(seed);
  }

  const planCount = db.prepare('SELECT COUNT(*) as c FROM training_plans').get() as { c: number };
  if (planCount.c === 0) {
    const planResult = db.prepare(
      'INSERT INTO training_plans (name, start_date, goal_date, goal_description, total_weeks, active) VALUES (?, ?, ?, ?, ?, 1)'
    ).run('Plan to Denver', '2026-02-01', '2026-07-01', 'Denver', 20);
    db.prepare('UPDATE sessions SET training_plan_id = ? WHERE training_plan_id IS NULL').run(planResult.lastInsertRowid);
  }
}
