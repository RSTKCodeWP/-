import { useEffect, useState } from 'react';

export type ScriptHealth =
  | { status: 'missing' }
  | { status: 'present'; version: number; ageMs: number }
  | { status: 'stale'; version: number; ageMs: number };

/**
 * Subscribes to AD_HB script-health push events from the main process.
 *
 * - 'missing': no heartbeat ever received on this connection
 * - 'present': heartbeat seen within the health window (script is running)
 * - 'stale':   heartbeat seen but more than ~5s ago (script may have crashed)
 *
 * Uses a module-level cache + single IPC listener so components that mount
 * AFTER the heartbeat arrived still see the current status. Without this
 * cache, a late-mounting popup would sit at 'missing' forever because main
 * only re-emits on status TRANSITIONS, never replays the current state.
 */

let cachedHealth: ScriptHealth = { status: 'missing' };
const subscribers = new Set<(h: ScriptHealth) => void>();
let bridgeUnsub: (() => void) | null = null;

function ensureBridge(): void {
  if (bridgeUnsub) return;
  const api = window.electronAPI;
  if (!api?.onScriptHealthChanged) return;
  bridgeUnsub = api.onScriptHealthChanged((next) => {
    cachedHealth = next as ScriptHealth;
    for (const cb of subscribers) {
      try { cb(cachedHealth); } catch { /* ignore */ }
    }
  });
}

export function useScriptHealth(): ScriptHealth {
  const [health, setHealth] = useState<ScriptHealth>(cachedHealth);

  useEffect(() => {
    ensureBridge();
    subscribers.add(setHealth);
    // Re-sync to latest in case it changed between render and effect.
    setHealth(cachedHealth);
    return () => { subscribers.delete(setHealth); };
  }, []);

  return health;
}
