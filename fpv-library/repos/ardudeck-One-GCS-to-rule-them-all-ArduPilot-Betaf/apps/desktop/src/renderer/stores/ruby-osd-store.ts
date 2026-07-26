/**
 * RubyFPV OSD editor state. Holds the RubyOsdParams being authored (which
 * built-in elements are on per screen, the layout preset, font size and
 * transparency), plus which of the 5 screens is currently being edited.
 * Persisted to localStorage so a design survives reloads. All mutations go
 * through the pure ruby-osd helpers so the model stays valid and serialisable.
 */

import { create } from 'zustand';
import {
  type RubyOsdParams,
  defaultRubyOsdParams,
  withElementEnabled,
  isElementEnabled,
  applyPreset,
  getFontSize,
  getTransparency,
  RUBY_OSD_PRESET,
} from '../utils/osd/ruby-osd';

const STORAGE_KEY = 'ardudeck.rubyosd.v1';

/** A populated starting point: the Default preset applied to every screen. */
function freshParams(): RubyOsdParams {
  let p = defaultRubyOsdParams();
  for (let i = 0; i < p.screens.length; i++) p = applyPreset(p, i, RUBY_OSD_PRESET.DEFAULT);
  return p;
}

function load(): RubyOsdParams {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw) as RubyOsdParams;
      // Guard against older/partial shapes.
      if (p && Array.isArray(p.screens) && p.screens.length === defaultRubyOsdParams().screens.length) return p;
    }
  } catch {
    /* ignore */
  }
  return freshParams();
}

interface RubyOsdStore {
  params: RubyOsdParams;
  /** Which of the 5 screens is being edited (0-based). */
  editingScreen: number;

  setEditingScreen: (i: number) => void;
  setCurrentScreen: (i: number) => void;
  toggleElement: (id: string) => void;
  setElement: (id: string, on: boolean) => void;
  setPreset: (preset: number) => void;
  setFontSize: (size: number) => void;
  setTransparency: (t: number) => void;
  reset: () => void;
}

function persist(get: () => RubyOsdStore) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(get().params));
  } catch {
    /* best effort */
  }
}

/** Mutate the currently-edited screen's preferences packing. */
function packPref(prefs: number, byteIndex: 0 | 1, value: number): number {
  const shift = byteIndex * 8;
  const mask = 0xff << shift;
  return (((prefs >>> 0) & ~mask) | ((value & 0xff) << shift)) >>> 0;
}

/** Deviating from a preset makes that screen "Custom" (matches RubyFPV). */
function markCustom(params: RubyOsdParams, screen: number): RubyOsdParams {
  const screens = params.screens.map((s, i) => (i === screen ? { ...s, layoutPreset: RUBY_OSD_PRESET.CUSTOM } : s));
  return { ...params, screens };
}

export const useRubyOsdStore = create<RubyOsdStore>((set, get) => ({
  params: load(),
  editingScreen: 0,

  setEditingScreen: (i) => set({ editingScreen: Math.max(0, Math.min(get().params.screens.length - 1, i)) }),

  setCurrentScreen: (i) => {
    set((s) => ({ params: { ...s.params, currentScreen: Math.max(0, Math.min(s.params.screens.length - 1, i)) } }));
    persist(get);
  },

  toggleElement: (id) => {
    const { params, editingScreen } = get();
    set({ params: markCustom(withElementEnabled(params, editingScreen, id, !isElementEnabled(params, editingScreen, id)), editingScreen) });
    persist(get);
  },

  setElement: (id, on) => {
    const { params, editingScreen } = get();
    set({ params: markCustom(withElementEnabled(params, editingScreen, id, on), editingScreen) });
    persist(get);
  },

  setPreset: (preset) => {
    set((s) => ({ params: applyPreset(s.params, s.editingScreen, preset) }));
    persist(get);
  },

  setFontSize: (size) => {
    set((s) => {
      const screens = s.params.screens.map((sc, i) =>
        i === s.editingScreen ? { ...sc, preferences: packPref(sc.preferences, 0, size) } : { ...sc },
      );
      return { params: { ...s.params, screens } };
    });
    persist(get);
  },

  setTransparency: (t) => {
    set((s) => {
      const screens = s.params.screens.map((sc, i) =>
        i === s.editingScreen ? { ...sc, preferences: packPref(sc.preferences, 1, t) } : { ...sc },
      );
      return { params: { ...s.params, screens } };
    });
    persist(get);
  },

  reset: () => {
    set({ params: freshParams(), editingScreen: 0 });
    persist(get);
  },
}));

// Re-export unpackers for the panel UI.
export { getFontSize, getTransparency };
