const STORAGE_KEY = 'ardudeck-sitl-profile-memory-v1';

/**
 * Per-SITL-instance memory: which profile was last applied, when, and a hint
 * at the last snapshot. Keyed by a stable instance id (the SITL profile name
 * from the launcher, e.g. "plane-stable").
 */
export interface SitlMemory {
  instanceKey: string;
  activeProfileId: string | null;
  lastAppliedAt: string | null;
  lastSnapshotId: string | null;
}

interface MemoryFile {
  byInstance: Record<string, SitlMemory>;
}

function read(): MemoryFile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { byInstance: {} };
    const parsed = JSON.parse(raw) as MemoryFile;
    return parsed.byInstance ? parsed : { byInstance: {} };
  } catch {
    return { byInstance: {} };
  }
}

function write(file: MemoryFile) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(file));
  } catch (err) {
    console.error('[sitl-stickiness] Failed to persist:', err);
  }
}

export function recordSitlApply(args: {
  instanceKey: string;
  profileId: string;
  snapshotId: string;
}): void {
  const file = read();
  file.byInstance[args.instanceKey] = {
    instanceKey: args.instanceKey,
    activeProfileId: args.profileId,
    lastAppliedAt: new Date().toISOString(),
    lastSnapshotId: args.snapshotId,
  };
  write(file);
}

export function getSitlMemory(instanceKey: string): SitlMemory | null {
  const file = read();
  return file.byInstance[instanceKey] ?? null;
}

export function clearSitlMemory(instanceKey: string): void {
  const file = read();
  delete file.byInstance[instanceKey];
  write(file);
}
