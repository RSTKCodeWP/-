import type { ProfileSnapshot } from './types.js';

const STORAGE_KEY = 'ardudeck-profile-snapshots-v1';
const MAX_PER_PROFILE = 50;

interface SnapshotFile {
  byProfile: Record<string, ProfileSnapshot[]>;  // most-recent first
}

function read(): SnapshotFile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { byProfile: {} };
    const parsed = JSON.parse(raw) as SnapshotFile;
    if (!parsed.byProfile) return { byProfile: {} };
    return parsed;
  } catch {
    return { byProfile: {} };
  }
}

function write(file: SnapshotFile) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(file));
  } catch (err) {
    console.error('[snapshots] Failed to persist:', err);
  }
}

/** Append a snapshot, keeping only the last MAX_PER_PROFILE per profile. */
export function storeSnapshot(snapshot: ProfileSnapshot): void {
  const file = read();
  const list = file.byProfile[snapshot.profileId] ?? [];
  list.unshift(snapshot);
  if (list.length > MAX_PER_PROFILE) list.length = MAX_PER_PROFILE;
  file.byProfile[snapshot.profileId] = list;
  write(file);
}

export function listSnapshots(profileId: string): ProfileSnapshot[] {
  const file = read();
  return file.byProfile[profileId] ?? [];
}

export function getSnapshot(profileId: string, snapshotId: string): ProfileSnapshot | undefined {
  return listSnapshots(profileId).find(s => s.id === snapshotId);
}

export function deleteSnapshot(profileId: string, snapshotId: string): void {
  const file = read();
  const list = file.byProfile[profileId];
  if (!list) return;
  file.byProfile[profileId] = list.filter(s => s.id !== snapshotId);
  write(file);
}

/**
 * Make a fresh snapshot object. The caller decides when to `storeSnapshot()` it
 * (typically after the compare modal actually applies).
 */
export function buildSnapshot(args: {
  profileId: string;
  templateSlug: string;
  target: ProfileSnapshot['target'];
  before: Record<string, number>;
  applied: Record<string, number>;
  reason: string;
}): ProfileSnapshot {
  return {
    id: `snap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    profileId: args.profileId,
    templateSlug: args.templateSlug,
    createdAt: new Date().toISOString(),
    target: args.target,
    before: args.before,
    applied: args.applied,
    reason: args.reason,
  };
}
