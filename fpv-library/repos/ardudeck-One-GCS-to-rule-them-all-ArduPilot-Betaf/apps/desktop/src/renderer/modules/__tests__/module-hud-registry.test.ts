import { describe, it, expect, beforeEach } from 'vitest';
import {
  registerModuleHudInstrument,
  unregisterModuleHudInstrument,
  unregisterModuleHudInstruments,
  listModuleHudInstruments,
  subscribeModuleHudInstruments,
} from '../module-hud-registry';
import { useHudStore } from '../../stores/hud-store';

const SLUG = 'com.example.test';
const ID = 'com.example.test.ccrp-hud';

beforeEach(() => {
  unregisterModuleHudInstruments(SLUG);
});

describe('module-hud-registry', () => {
  it('registers, lists, and unregisters an instrument', () => {
    registerModuleHudInstrument(SLUG, { id: ID, label: 'CCRP release cue' });
    expect(listModuleHudInstruments().map((i) => i.id)).toContain(ID);
    unregisterModuleHudInstrument(SLUG, ID);
    expect(listModuleHudInstruments().map((i) => i.id)).not.toContain(ID);
  });

  it('notifies subscribers on register', () => {
    let hits = 0;
    const unsub = subscribeModuleHudInstruments(() => { hits += 1; });
    registerModuleHudInstrument(SLUG, { id: ID, label: 'x' });
    unsub();
    expect(hits).toBe(1);
  });

  it('rejects an instrument without an id', () => {
    expect(() => registerModuleHudInstrument(SLUG, { id: '', label: 'x' })).toThrow();
  });
});

describe('hud-store module instrument toggle', () => {
  it('defaults off and toggles on/off', () => {
    const s = useHudStore.getState();
    expect(s.isModuleInstrumentEnabled(ID)).toBe(false);
    s.toggleModuleInstrument(ID);
    expect(useHudStore.getState().isModuleInstrumentEnabled(ID)).toBe(true);
    useHudStore.getState().toggleModuleInstrument(ID);
    expect(useHudStore.getState().isModuleInstrumentEnabled(ID)).toBe(false);
  });
});
