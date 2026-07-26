CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  time_start TEXT,
  time_end TEXT,
  location TEXT NOT NULL DEFAULT 'home-room-A',
  platform TEXT NOT NULL DEFAULT 'Air65',
  weather TEXT NOT NULL DEFAULT 'indoor',
  session_type TEXT NOT NULL DEFAULT 'blocked-drill',
  notes TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS packs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  pack_number INTEGER NOT NULL DEFAULT 1,
  voltage_start REAL,
  voltage_end REAL,
  focus TEXT DEFAULT '',
  crashes INTEGER DEFAULT 0,
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tricks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  level INTEGER NOT NULL DEFAULT 1,
  category TEXT NOT NULL DEFAULT 'combo',
  description TEXT DEFAULT '',
  indoor_notes TEXT DEFAULT '',
  reference_links TEXT DEFAULT '[]',
  prerequisites TEXT DEFAULT '[]',
  phase_introduced INTEGER NOT NULL DEFAULT 1,
  is_custom INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trick_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  trick_id INTEGER NOT NULL REFERENCES tricks(id),
  attempts INTEGER NOT NULL DEFAULT 0,
  landed INTEGER NOT NULL DEFAULT 0,
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS crashes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  pack_number INTEGER,
  trick_id INTEGER REFERENCES tricks(id),
  failure_type TEXT NOT NULL DEFAULT 'orient',
  root_cause TEXT NOT NULL DEFAULT 'pilot',
  action_item TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
  good_1 TEXT DEFAULT '',
  good_2 TEXT DEFAULT '',
  good_3 TEXT DEFAULT '',
  improve_1 TEXT DEFAULT '',
  improve_2 TEXT DEFAULT '',
  improve_3 TEXT DEFAULT '',
  fatigue TEXT DEFAULT 'good',
  frustration TEXT DEFAULT 'none',
  stopped_before_bad INTEGER DEFAULT 1,
  tomorrow_focus TEXT DEFAULT '',
  sim_drill_tonight TEXT DEFAULT '',
  dvr_timestamps TEXT DEFAULT '',
  blackbox_recorded INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS weekly_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week_number INTEGER NOT NULL,
  date_start TEXT,
  date_end TEXT,
  phase TEXT NOT NULL DEFAULT '1-indoor',
  sessions_real INTEGER DEFAULT 0,
  sessions_sim INTEGER DEFAULT 0,
  sessions_dvr INTEGER DEFAULT 0,
  total_packs INTEGER DEFAULT 0,
  total_sim_minutes INTEGER DEFAULT 0,
  biggest_insight TEXT DEFAULT '',
  pattern_noticed TEXT DEFAULT '',
  next_week_priority TEXT DEFAULT '',
  ready_to_advance INTEGER DEFAULT 0,
  blocker TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mastery_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  weekly_review_id INTEGER NOT NULL REFERENCES weekly_reviews(id) ON DELETE CASCADE,
  trick_id INTEGER NOT NULL REFERENCES tricks(id),
  success_rate REAL,
  hold_time_seconds REAL,
  clean_laps INTEGER,
  variance_seconds REAL,
  status TEXT NOT NULL DEFAULT 'not-started',
  trend TEXT DEFAULT 'flat',
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS gate_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phase INTEGER NOT NULL,
  item_text TEXT NOT NULL,
  is_hard_gate INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gate_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gate_check_id INTEGER NOT NULL REFERENCES gate_checks(id),
  met INTEGER NOT NULL DEFAULT 0,
  date_met TEXT
);

CREATE TABLE IF NOT EXISTS equipment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL DEFAULT 'other',
  name TEXT NOT NULL,
  platform TEXT DEFAULT '',
  quantity_in_stock INTEGER DEFAULT 0,
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS equipment_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
  session_id INTEGER REFERENCES sessions(id),
  date TEXT NOT NULL,
  action TEXT NOT NULL DEFAULT 'inspected',
  notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS denver_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL,
  text TEXT NOT NULL,
  completed INTEGER DEFAULT 0,
  notes TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS drills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  mastery_criteria TEXT DEFAULT '',
  related_tricks TEXT DEFAULT '[]',
  space_required TEXT DEFAULT 'indoor-small'
);

CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'website',
  url TEXT NOT NULL,
  description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS week_schedule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week_number INTEGER NOT NULL,
  phase INTEGER NOT NULL,
  primary_drills TEXT DEFAULT '',
  target TEXT DEFAULT '',
  sim_focus TEXT DEFAULT '',
  go_nogo TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS training_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  goal_date TEXT,
  goal_description TEXT,
  total_weeks INTEGER NOT NULL DEFAULT 20,
  active INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
