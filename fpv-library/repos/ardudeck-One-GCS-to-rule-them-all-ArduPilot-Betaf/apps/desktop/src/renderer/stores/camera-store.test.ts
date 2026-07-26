import { describe, it, expect } from 'vitest';
import { osdBackdropSource } from './camera-store';
import type { CameraSourceConfig } from '../../shared/camera-types';

function src(id: string, vehicleKey: string): CameraSourceConfig {
  return { id, vehicleKey, kind: 'rtsp', label: id, url: `rtsp://x/${id}` };
}

/** Minimal state slice the selector reads. */
function state(sources: CameraSourceConfig[], selected: Record<string, string>) {
  return {
    sources: Object.fromEntries(sources.map((s) => [s.id, s])),
    selectedByVehicle: selected,
  } as Parameters<typeof osdBackdropSource>[0];
}

describe('osdBackdropSource', () => {
  it('returns null when no vehicle is targeted', () => {
    expect(osdBackdropSource(state([], {}), null)).toBeNull();
  });

  it('returns null when the vehicle has no selected source', () => {
    const s = state([src('a', 'veh1')], {});
    expect(osdBackdropSource(s, 'veh1')).toBeNull();
  });

  it('returns null when the selected source id is dangling', () => {
    const s = state([src('a', 'veh1')], { veh1: 'missing' });
    expect(osdBackdropSource(s, 'veh1')).toBeNull();
  });

  it('returns the selected source for the target vehicle', () => {
    const a = src('a', 'veh1');
    const s = state([a], { veh1: 'a' });
    expect(osdBackdropSource(s, 'veh1')).toEqual(a);
  });
});
