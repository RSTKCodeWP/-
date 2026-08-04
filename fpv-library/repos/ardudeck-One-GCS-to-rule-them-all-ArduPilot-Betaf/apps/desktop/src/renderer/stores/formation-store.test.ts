/**
 * Formation geometry is PER FLEET. A single shared shape/spacing/altStep made every
 * fleet's glyph bar light up together ("selecting a formation on one fleet flips it on
 * the others") and let any later re-issue of another fleet's follow.leader push the
 * last-touched fleet's geometry onto it.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  useFormationStore,
  formationConfigOf,
  DEFAULT_FORMATION_CONFIG,
} from './formation-store';

const A = 'transport-1:1:1';
const B = 'transport-1:2:1';

function cfg(leaderKey: string | null) {
  const s = useFormationStore.getState();
  return formationConfigOf(s.byFleet, s.defaults, leaderKey);
}

describe('per-fleet formation geometry', () => {
  beforeEach(() => {
    useFormationStore.setState({ defaults: DEFAULT_FORMATION_CONFIG, byFleet: {}, busy: false, contextMenu: null });
  });

  it('does not leak one fleet\'s shape onto another', () => {
    useFormationStore.getState().setConfig(A, { shape: 'column' });

    expect(cfg(A).shape).toBe('column');
    // B never touched: it must still read its own (default) shape, not A's.
    expect(cfg(B).shape).toBe('vee');
  });

  it('keeps spacing and altStep independent per fleet', () => {
    useFormationStore.getState().setConfig(A, { spacing: 40, altStep: 12 });
    useFormationStore.getState().setConfig(B, { spacing: 8 });

    expect(cfg(A)).toEqual({ shape: 'vee', spacing: 40, altStep: 12 });
    expect(cfg(B)).toEqual({ shape: 'vee', spacing: 8, altStep: 5 });
  });

  it('a fleet with no entry inherits the defaults but does not alias them', () => {
    useFormationStore.getState().setConfig(null, { shape: 'box', spacing: 25 });
    expect(cfg(A)).toEqual({ shape: 'box', spacing: 25, altStep: 5 });

    // Patching the fleet must not write back into the defaults.
    useFormationStore.getState().setConfig(A, { shape: 'diamond' });
    expect(cfg(A).shape).toBe('diamond');
    expect(useFormationStore.getState().defaults.shape).toBe('box');
  });

  it('patches merge instead of replacing the other axes', () => {
    useFormationStore.getState().setConfig(A, { shape: 'survey', spacing: 40 });
    useFormationStore.getState().setConfig(A, { altStep: 3 });
    expect(cfg(A)).toEqual({ shape: 'survey', spacing: 40, altStep: 3 });
  });

  it('a disbanded fleet forgets its geometry, and only its own', () => {
    useFormationStore.getState().setConfig(A, { shape: 'echelonLeft' });
    useFormationStore.getState().setConfig(B, { shape: 'line' });

    useFormationStore.getState().dropConfig(A);
    expect(cfg(A).shape).toBe('vee'); // back to the defaults
    expect(cfg(B).shape).toBe('line'); // untouched

    useFormationStore.getState().clearConfigs();
    expect(useFormationStore.getState().byFleet).toEqual({});
  });

  it('dropping an unknown fleet leaves the map identical', () => {
    useFormationStore.getState().setConfig(A, { shape: 'line' });
    const before = useFormationStore.getState().byFleet;
    useFormationStore.getState().dropConfig('nobody');
    // Same object identity: no spurious re-render for every fleet row.
    expect(useFormationStore.getState().byFleet).toBe(before);
  });
});
