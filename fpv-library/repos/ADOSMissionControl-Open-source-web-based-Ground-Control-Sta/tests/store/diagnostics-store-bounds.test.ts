import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useDiagnosticsStore } from '@/stores/diagnostics-store';

/**
 * logMessage runs on every inbound frame regardless of whether the rate panel
 * is mounted (updateRates only runs while it is open). The per-message
 * timestamps array must therefore be bounded at push time, not by updateRates.
 */
describe('diagnostics-store message-rate timestamp bounds', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useDiagnosticsStore.getState().clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('caps a high-rate stream at the hard ceiling without updateRates', () => {
    vi.setSystemTime(1_000_000);
    // 5000 pushes at the same instant — far above any real window count.
    for (let i = 0; i < 5000; i++) {
      useDiagnosticsStore.getState().logMessage(30, 'ATTITUDE', 'in', 28);
    }
    const entry = useDiagnosticsStore.getState().messageRates.get(30);
    expect(entry).toBeDefined();
    expect(entry!.timestamps.length).toBeLessThanOrEqual(600);
    expect(entry!.timestamps.length).toBeGreaterThan(0);
  });

  it('prunes timestamps older than the rate window at push time', () => {
    vi.setSystemTime(1_000_000);
    for (let i = 0; i < 50; i++) {
      useDiagnosticsStore.getState().logMessage(33, 'GLOBAL_POSITION_INT', 'in', 28);
    }
    // Advance well past the 5 s rate window and push once more.
    vi.setSystemTime(1_000_000 + 60_000);
    useDiagnosticsStore.getState().logMessage(33, 'GLOBAL_POSITION_INT', 'in', 28);

    const entry = useDiagnosticsStore.getState().messageRates.get(33);
    expect(entry).toBeDefined();
    // The 50 stale timestamps are dropped on the next push; only the fresh one
    // survives, so a stopped-then-resumed stream does not pin a stale array.
    expect(entry!.timestamps.length).toBe(1);
    expect(entry!.timestamps[0]).toBe(1_000_000 + 60_000);
  });
});
