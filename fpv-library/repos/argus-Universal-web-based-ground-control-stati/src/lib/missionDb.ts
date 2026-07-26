import type { Waypoint, RallyPoint } from './types';

export interface MissionRecord {
  id: string;
  name: string;
  waypoints: Waypoint[];
  fence: { lat: number; lon: number }[];
  rally: RallyPoint[];
  defaultAlt: number;
  createdAt: number;
}

const DB_NAME = 'argus-missions';
const DB_VERSION = 1;
const STORE_NAME = 'missions';

let _db: IDBDatabase | null = null;

function open(): Promise<IDBDatabase> {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        store.createIndex('name', 'name', { unique: false });
        store.createIndex('createdAt', 'createdAt', { unique: false });
      }
    };
    req.onsuccess = () => {
      _db = req.result;
      resolve(_db);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function saveMission(
  name: string,
  data: { waypoints: Waypoint[]; fence: { lat: number; lon: number }[]; rally: RallyPoint[]; defaultAlt: number },
): Promise<string> {
  const db = await open();
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const record: MissionRecord = { id, name, ...data, createdAt: Date.now() };
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put(record);
    tx.oncomplete = () => resolve(id);
    tx.onerror = () => reject(tx.error);
  });
}

export async function loadMission(id: string): Promise<MissionRecord | null> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const req = tx.objectStore(STORE_NAME).get(id);
    req.onsuccess = () => resolve(req.result ?? null);
    req.onerror = () => reject(req.error);
  });
}

export async function listMissions(): Promise<MissionRecord[]> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const req = tx.objectStore(STORE_NAME).index('createdAt').getAll();
    req.onsuccess = () => resolve((req.result as MissionRecord[]).reverse());
    req.onerror = () => reject(req.error);
  });
}

export async function deleteMission(id: string): Promise<void> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function updateMissionName(id: string, name: string): Promise<void> {
  const record = await loadMission(id);
  if (!record) return;
  record.name = name;
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
