import { describe, it, expect } from 'vitest';
import { shouldMirrorToSharedStore } from './telemetry-routing';

describe('shouldMirrorToSharedStore', () => {
  it('always mirrors the legacy primary key', () => {
    expect(shouldMirrorToSharedStore('__primary__', null, null)).toBe(true);
    expect(shouldMirrorToSharedStore('__primary__', 'veh-2', 'veh-1')).toBe(true);
  });

  it('single vehicle before anything is seen: accept', () => {
    expect(shouldMirrorToSharedStore('veh-1', null, null)).toBe(true);
  });

  it('locks onto the first-seen vehicle when none is active (no looping)', () => {
    const firstSeen = 'veh-1';
    expect(shouldMirrorToSharedStore('veh-1', null, firstSeen)).toBe(true);
    // A second fleet vehicle must NOT overwrite the shared store -> no map hop.
    expect(shouldMirrorToSharedStore('veh-2', null, firstSeen)).toBe(false);
    expect(shouldMirrorToSharedStore('veh-3', null, firstSeen)).toBe(false);
  });

  it('explicit active vehicle wins over first-seen', () => {
    expect(shouldMirrorToSharedStore('veh-2', 'veh-2', 'veh-1')).toBe(true);
    expect(shouldMirrorToSharedStore('veh-1', 'veh-2', 'veh-1')).toBe(false);
  });

  it('switching active vehicle cleanly redirects the shared store', () => {
    // active = veh-3: only veh-3 mirrors, the rest are filtered.
    expect(shouldMirrorToSharedStore('veh-3', 'veh-3', 'veh-1')).toBe(true);
    expect(shouldMirrorToSharedStore('veh-1', 'veh-3', 'veh-1')).toBe(false);
    expect(shouldMirrorToSharedStore('veh-2', 'veh-3', 'veh-1')).toBe(false);
  });
});
