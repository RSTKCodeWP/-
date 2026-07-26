/**
 * Heartbeat tracker for ArduDeck-managed Lua scripts.
 *
 * Listens for the script's NAMED_VALUE_FLOAT 'AD_HB' = SCRIPT_VERSION beacon.
 * The script publishes this every ~1 second. We track the most recent value
 * and the wall-clock timestamp of the last reception.
 *
 * Three states the rest of the system cares about:
 *   - present:   heartbeat seen within HEALTH_WINDOW_MS, version matches expected
 *   - stale:     heartbeat seen but more than HEALTH_WINDOW_MS ago (script may
 *                have crashed, or vehicle disconnected)
 *   - missing:   never seen since last reset / current connection
 *
 * Callers (the installer flow, the command popup) can ask for status without
 * triggering any FC traffic - this is a passive listener.
 */

const HEARTBEAT_NAME = 'AD_HB';
const HEALTH_WINDOW_MS = 5000;
const STALE_CHECK_INTERVAL_MS = 1500;

interface HeartbeatRecord {
  /** Last observed script version (the float value). */
  version: number;
  /** Wall-clock ms when we last received it. */
  receivedAt: number;
}

let lastHeartbeat: HeartbeatRecord | null = null;
let lastEmittedStatus: ScriptHealth['status'] | null = null;
let staleCheckTimer: NodeJS.Timeout | null = null;
const subscribers = new Set<(health: ScriptHealth) => void>();

export type ScriptHealth =
  | { status: 'missing' }
  | { status: 'present'; version: number; ageMs: number }
  | { status: 'stale'; version: number; ageMs: number };

/**
 * Feed a NAMED_VALUE_FLOAT into the tracker. The MAVLink RX pipeline calls
 * this for every NVF; we cheaply skip non-AD_HB names.
 */
export function ingestNamedValueFloat(name: string, value: number): void {
  if (name !== HEARTBEAT_NAME) return;
  lastHeartbeat = { version: value, receivedAt: Date.now() };
  emitIfChanged();
  ensureStaleChecker();
}

/**
 * Subscribe to script-health transitions. The callback fires once immediately
 * with the current status, and again whenever status changes (missing→present,
 * present→stale, stale→present, etc).
 *
 * Returns an unsubscribe function.
 */
export function subscribeHealth(callback: (health: ScriptHealth) => void): () => void {
  subscribers.add(callback);
  callback(getScriptHealth());
  return () => { subscribers.delete(callback); };
}

function emitIfChanged(): void {
  const current = getScriptHealth();
  if (current.status === lastEmittedStatus) return;
  lastEmittedStatus = current.status;
  for (const cb of subscribers) {
    try { cb(current); } catch { /* swallow subscriber errors */ }
  }
}

function ensureStaleChecker(): void {
  // Periodic check so the present→stale transition fires even when no NVF
  // arrives. Lazily started; cleared by reset.
  if (staleCheckTimer) return;
  staleCheckTimer = setInterval(emitIfChanged, STALE_CHECK_INTERVAL_MS);
}

export function getScriptHealth(): ScriptHealth {
  if (!lastHeartbeat) return { status: 'missing' };
  const ageMs = Date.now() - lastHeartbeat.receivedAt;
  if (ageMs <= HEALTH_WINDOW_MS) {
    return { status: 'present', version: lastHeartbeat.version, ageMs };
  }
  return { status: 'stale', version: lastHeartbeat.version, ageMs };
}

/**
 * Reset on FC disconnect / new connection. Avoids stale heartbeat surviving
 * a connection swap to a different vehicle.
 */
export function resetHeartbeat(): void {
  lastHeartbeat = null;
  if (staleCheckTimer) {
    clearInterval(staleCheckTimer);
    staleCheckTimer = null;
  }
  emitIfChanged();
}

/**
 * Wait for a fresh heartbeat (received after the call) up to `timeoutMs`.
 * Used by the installer flow to verify the script started running after upload.
 *
 * Resolves with the version on success, null on timeout.
 */
export function waitForHeartbeat(timeoutMs: number): Promise<number | null> {
  const deadline = Date.now() + timeoutMs;
  const startedAt = Date.now();

  return new Promise<number | null>((resolve) => {
    const tick = () => {
      if (lastHeartbeat && lastHeartbeat.receivedAt >= startedAt) {
        resolve(lastHeartbeat.version);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(null);
        return;
      }
      setTimeout(tick, 200);
    };
    tick();
  });
}
