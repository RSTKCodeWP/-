/**
 * HUD configuration store — the editable state behind the green fighter HUD
 * (which widgets show, style, units, scale, movable-widget positions) plus
 * named presets. Persisted to localStorage so a HUD you build survives reloads
 * and applies to both the OSD Designer preview and the live video overlay.
 */

import { create } from 'zustand';
import {
  type HudConfig,
  type HudWidgetId,
  type HudColor,
  type HudUnits,
  type HudProfile,
  type Vec2,
  DEFAULT_HUD_CONFIG,
  DEFAULT_POSITIONS,
  normalizeHudConfig,
} from '../components/camera/hud/hud-config';

const STORAGE_KEY = 'ardudeck.hud.v1';

interface Persisted {
  config: HudConfig;
  presets: Record<string, HudConfig>;
}

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Persisted>;
      const presets: Record<string, HudConfig> = {};
      for (const [k, v] of Object.entries(p.presets ?? {})) presets[k] = normalizeHudConfig(v);
      return { config: normalizeHudConfig(p.config), presets };
    }
  } catch {
    /* ignore */
  }
  return { config: normalizeHudConfig(DEFAULT_HUD_CONFIG), presets: {} };
}

const initial = load();

interface HudStore {
  config: HudConfig;
  presets: Record<string, HudConfig>;
  /** Which arrangement the designer is editing/previewing (not persisted). */
  designGround: boolean;

  toggleWidget: (id: HudWidgetId, ground?: boolean) => void;
  /** Toggle a module-contributed HUD instrument (see module-hud-registry). */
  toggleModuleInstrument: (id: string) => void;
  /** Whether a module-contributed instrument is currently on. */
  isModuleInstrumentEnabled: (id: string) => boolean;
  setProfile: (p: HudProfile) => void;
  setDesignGround: (g: boolean) => void;
  setColor: (c: HudColor) => void;
  setLineWeight: (w: number) => void;
  setGlow: (g: boolean) => void;
  setUnits: (u: HudUnits) => void;
  setScale: (s: number) => void;
  setPosition: (id: string, pos: Vec2) => void;
  resetConfig: () => void;

  savePreset: (name: string) => void;
  loadPreset: (name: string) => void;
  deletePreset: (name: string) => void;
}

function persist(get: () => HudStore) {
  try {
    const { config, presets } = get();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ config, presets }));
  } catch {
    /* best effort */
  }
}

export const useHudStore = create<HudStore>((set, get) => ({
  config: initial.config,
  presets: initial.presets,
  designGround: false,

  toggleWidget: (id, ground = false) => {
    set((s) => {
      const key = ground ? 'widgetsGround' : 'widgets';
      return { config: { ...s.config, [key]: { ...s.config[key], [id]: !s.config[key][id] } } };
    });
    persist(get);
  },
  toggleModuleInstrument: (id) => {
    set((s) => ({
      config: {
        ...s.config,
        moduleInstruments: { ...s.config.moduleInstruments, [id]: !s.config.moduleInstruments[id] },
      },
    }));
    persist(get);
  },
  isModuleInstrumentEnabled: (id) => !!get().config.moduleInstruments[id],
  setProfile: (profile) => { set((s) => ({ config: { ...s.config, profile } })); persist(get); },
  setDesignGround: (designGround) => set({ designGround }),
  setColor: (color) => { set((s) => ({ config: { ...s.config, color } })); persist(get); },
  setLineWeight: (lineWeight) => { set((s) => ({ config: { ...s.config, lineWeight } })); persist(get); },
  setGlow: (glow) => { set((s) => ({ config: { ...s.config, glow } })); persist(get); },
  setUnits: (units) => { set((s) => ({ config: { ...s.config, units } })); persist(get); },
  setScale: (scale) => { set((s) => ({ config: { ...s.config, scale } })); persist(get); },
  setPosition: (id, pos) => {
    set((s) => ({ config: { ...s.config, positions: { ...s.config.positions, [id]: pos } } }));
    persist(get);
  },
  resetConfig: () => {
    set({ config: normalizeHudConfig(DEFAULT_HUD_CONFIG) });
    persist(get);
  },

  savePreset: (name) => {
    const n = name.trim();
    if (!n) return;
    set((s) => ({ presets: { ...s.presets, [n]: { ...s.config, positions: { ...s.config.positions } } } }));
    persist(get);
  },
  loadPreset: (name) => {
    const p = get().presets[name];
    if (p) { set({ config: normalizeHudConfig(p) }); persist(get); }
  },
  deletePreset: (name) => {
    set((s) => {
      const next = { ...s.presets };
      delete next[name];
      return { presets: next };
    });
    persist(get);
  },
}));

export { DEFAULT_POSITIONS };
