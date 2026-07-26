import { DB, type QueryParameter } from "https://deno.land/x/sqlite@v3.9.1/mod.ts";

export type PartStatus = "unused" | "in-use" | "broken" | "retired" | "lost";
export type PartType =
  | "motor"
  | "fc"
  | "esc"
  | "vtx"
  | "frame"
  | "camera"
  | "antenna"
  | "battery"
  | "craft"
  | "gear"
  | "other";

export interface Part {
  id: number;
  name: string;
  status: PartStatus;
  type: PartType | null;
  notes: string | null;
  specs: string | null;
  quantity: number;
  parent_id: number | null;
  photo_path: string | null;
  serial_number: string | null;
  warranty_expiry: string | null;
  purchase_date: string | null;
  purchase_price: number | null;
  created_at: string;
  updated_at: string;
}

export interface HistoryEntry {
  id: number;
  part_id: number;
  action: string;
  from_parent_id: number | null;
  to_parent_id: number | null;
  old_status: string | null;
  new_status: string | null;
  quantity_delta: number | null;
  notes: string | null;
  created_at: string;
}

export interface CreatePartInput {
  name: string;
  quantity: number;
  status: PartStatus;
  type?: PartType | null;
  notes?: string;
  specs?: string;
  parent_id?: number | null;
  serial_number?: string | null;
  warranty_expiry?: string | null;
  purchase_date?: string | null;
  purchase_price?: number | null;
}

export interface UpdatePartInput {
  name?: string;
  status?: PartStatus;
  type?: PartType | null;
  notes?: string;
  specs?: string;
  quantity?: number;
  photo_path?: string;
  serial_number?: string | null;
  warranty_expiry?: string | null;
  purchase_date?: string | null;
  purchase_price?: number | null;
}

export function runMigrations(db: DB): void {
  const columns = db.query<[number, string, string, number, string | null, number]>(
    "PRAGMA table_info(parts)",
  ).map((row) => row[1]);

  if (!columns.includes("type")) {
    db.execute("ALTER TABLE parts ADD COLUMN type TEXT");
  }
  if (!columns.includes("specs")) {
    db.execute("ALTER TABLE parts ADD COLUMN specs TEXT");
  }
  if (!columns.includes("serial_number")) {
    db.execute("ALTER TABLE parts ADD COLUMN serial_number TEXT");
  }
  if (!columns.includes("warranty_expiry")) {
    db.execute("ALTER TABLE parts ADD COLUMN warranty_expiry TEXT");
  }
  if (!columns.includes("purchase_date")) {
    db.execute("ALTER TABLE parts ADD COLUMN purchase_date TEXT");
  }
  if (!columns.includes("purchase_price")) {
    db.execute("ALTER TABLE parts ADD COLUMN purchase_price REAL");
  }
}

export function initDb(path: string): DB {
  const db = new DB(path);
  db.execute(`
    CREATE TABLE IF NOT EXISTS parts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'unused',
      type TEXT,
      notes TEXT,
      specs TEXT,
      quantity INTEGER NOT NULL DEFAULT 1,
      parent_id INTEGER REFERENCES parts(id),
      photo_path TEXT,
      serial_number TEXT,
      warranty_expiry TEXT,
      purchase_date TEXT,
      purchase_price REAL,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS part_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      part_id INTEGER NOT NULL REFERENCES parts(id),
      action TEXT NOT NULL,
      from_parent_id INTEGER REFERENCES parts(id),
      to_parent_id INTEGER REFERENCES parts(id),
      old_status TEXT,
      new_status TEXT,
      quantity_delta INTEGER,
      notes TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);
  runMigrations(db);
  return db;
}

export function createPart(db: DB, input: CreatePartInput): number {
  db.query(
    `INSERT INTO parts (name, quantity, status, type, notes, specs, parent_id, serial_number, warranty_expiry, purchase_date, purchase_price)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      input.name,
      input.quantity,
      input.status,
      input.type ?? null,
      input.notes ?? null,
      input.specs ?? null,
      input.parent_id ?? null,
      input.serial_number ?? null,
      input.warranty_expiry ?? null,
      input.purchase_date ?? null,
      input.purchase_price ?? null,
    ],
  );
  const id = db.lastInsertRowId;
  db.query(
    `INSERT INTO part_history (part_id, action, to_parent_id)
     VALUES (?, 'created', ?)`,
    [id, input.parent_id ?? null],
  );
  return id;
}

export function getPart(db: DB, id: number): Part | null {
  const rows = db.query<
    [
      number,
      string,
      string,
      string | null,
      string | null,
      string | null,
      number,
      number | null,
      string | null,
      string | null,
      string | null,
      string | null,
      number | null,
      string,
      string,
    ]
  >(
    `SELECT id, name, status, type, notes, specs, quantity, parent_id, photo_path, serial_number, warranty_expiry, purchase_date, purchase_price, created_at, updated_at
     FROM parts WHERE id = ?`,
    [id],
  );
  if (rows.length === 0) return null;
  const [
    pid,
    name,
    status,
    type,
    notes,
    specs,
    quantity,
    parent_id,
    photo_path,
    serial_number,
    warranty_expiry,
    purchase_date,
    purchase_price,
    created_at,
    updated_at,
  ] = rows[0];
  return {
    id: pid,
    name,
    status: status as PartStatus,
    type: type as PartType | null,
    notes,
    specs,
    quantity,
    parent_id,
    photo_path,
    serial_number,
    warranty_expiry,
    purchase_date,
    purchase_price,
    created_at,
    updated_at,
  };
}

export interface PartFilter {
  parent_id?: number | null;
  type?: PartType;
  status?: PartStatus;
  q?: string;
}

export function listParts(db: DB, filter: PartFilter = {}): Part[] {
  type Row = [
    number,
    string,
    string,
    string | null,
    string | null,
    string | null,
    number,
    number | null,
    string | null,
    string | null,
    string | null,
    string | null,
    number | null,
    string,
    string,
  ];
  const select =
    `SELECT id, name, status, type, notes, specs, quantity, parent_id, photo_path, serial_number, warranty_expiry, purchase_date, purchase_price, created_at, updated_at FROM parts`;

  const conditions: string[] = [];
  const params: QueryParameter[] = [];

  if (filter.parent_id !== undefined) {
    if (filter.parent_id === null) {
      conditions.push("parent_id IS NULL");
    } else {
      conditions.push("parent_id = ?");
      params.push(filter.parent_id);
    }
  }
  if (filter.type !== undefined) {
    conditions.push("type = ?");
    params.push(filter.type);
  }
  if (filter.status !== undefined) {
    conditions.push("status = ?");
    params.push(filter.status);
  }
  if (filter.q !== undefined) {
    conditions.push("instr(lower(name), lower(?)) > 0");
    params.push(filter.q);
  }

  const where = conditions.length > 0 ? ` WHERE ${conditions.join(" AND ")}` : "";
  const rows: Row[] = db.query(`${select}${where} ORDER BY name`, params);

  return rows.map((
    [
      id,
      name,
      status,
      partType,
      notes,
      specs,
      quantity,
      parent_id,
      photo_path,
      serial_number,
      warranty_expiry,
      purchase_date,
      purchase_price,
      created_at,
      updated_at,
    ],
  ) => ({
    id,
    name,
    status: status as PartStatus,
    type: partType as PartType | null,
    notes,
    specs,
    quantity,
    parent_id,
    photo_path,
    serial_number,
    warranty_expiry,
    purchase_date,
    purchase_price,
    created_at,
    updated_at,
  }));
}

export function updatePart(db: DB, id: number, input: UpdatePartInput): void {
  const current = getPart(db, id);
  if (!current) throw new Error(`Part ${id} not found`);

  const name = input.name ?? current.name;
  const status = input.status ?? current.status;
  const type = "type" in input ? (input.type ?? null) : current.type;
  const notes = "notes" in input ? (input.notes ?? null) : current.notes;
  const specs = "specs" in input
    ? (input.specs?.replace(/\r\n/g, "\n").trim() || null)
    : current.specs;
  const quantity = input.quantity ?? current.quantity;
  const photo_path = "photo_path" in input ? (input.photo_path ?? null) : current.photo_path;
  const serial_number = "serial_number" in input
    ? (input.serial_number ?? null)
    : current.serial_number;
  const warranty_expiry = "warranty_expiry" in input
    ? (input.warranty_expiry ?? null)
    : current.warranty_expiry;
  const purchase_date = "purchase_date" in input
    ? (input.purchase_date ?? null)
    : current.purchase_date;
  const purchase_price = "purchase_price" in input
    ? (input.purchase_price ?? null)
    : current.purchase_price;

  db.query(
    `UPDATE parts SET name=?, status=?, type=?, notes=?, specs=?, quantity=?, photo_path=?,
       serial_number=?, warranty_expiry=?, purchase_date=?, purchase_price=?, updated_at=datetime('now')
     WHERE id=?`,
    [
      name,
      status,
      type,
      notes,
      specs,
      quantity,
      photo_path,
      serial_number,
      warranty_expiry,
      purchase_date,
      purchase_price,
      id,
    ],
  );
  db.query(
    `INSERT INTO part_history (part_id, action, old_status, new_status, quantity_delta)
     VALUES (?, 'updated', ?, ?, ?)`,
    [id, current.status, status, quantity - current.quantity],
  );
}

export function movePart(db: DB, id: number, newParentId: number | null, notes?: string): void {
  const current = getPart(db, id);
  if (!current) throw new Error(`Part ${id} not found`);

  db.query(
    `UPDATE parts SET parent_id=?, updated_at=datetime('now') WHERE id=?`,
    [newParentId, id],
  );
  db.query(
    `INSERT INTO part_history (part_id, action, from_parent_id, to_parent_id, notes)
     VALUES (?, 'moved', ?, ?, ?)`,
    [id, current.parent_id, newParentId, notes ?? null],
  );
}

export function getPartHistory(db: DB, partId: number): HistoryEntry[] {
  const rows = db.query<
    [
      number,
      number,
      string,
      number | null,
      number | null,
      string | null,
      string | null,
      number | null,
      string | null,
      string,
    ]
  >(
    `SELECT id, part_id, action, from_parent_id, to_parent_id,
            old_status, new_status, quantity_delta, notes, created_at
     FROM part_history WHERE part_id = ? ORDER BY id ASC`,
    [partId],
  );
  return rows.map((
    [
      id,
      part_id,
      action,
      from_parent_id,
      to_parent_id,
      old_status,
      new_status,
      quantity_delta,
      notes,
      created_at,
    ],
  ) => ({
    id,
    part_id,
    action,
    from_parent_id,
    to_parent_id,
    old_status,
    new_status,
    quantity_delta,
    notes,
    created_at,
  }));
}

export { DB };
