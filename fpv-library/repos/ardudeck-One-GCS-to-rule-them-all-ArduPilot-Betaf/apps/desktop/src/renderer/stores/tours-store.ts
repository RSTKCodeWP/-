import { create } from 'zustand';

const STORAGE_KEY = 'ardudeck:tours:seen';

function loadSeen(): Set<string> {
  if (import.meta.env.DEV) {
    // Always start dev sessions fresh so every app run re-prompts.
    return new Set();
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((v): v is string => typeof v === 'string'));
  } catch {
    return new Set();
  }
}

function persist(seen: Set<string>) {
  if (import.meta.env.DEV) {
    // Skip persistence in dev so restarts always re-prompt.
    return;
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...seen]));
  } catch {
    // localStorage may be disabled; tours will simply re-prompt next session
  }
}

interface ToursStore {
  seen: Set<string>;
  skippedThisSession: Set<string>;
  activeTourId: string | null;
  promptTourId: string | null;
  /** Tour waiting to auto-start once a connection is established (user chose "use my FC"). */
  pendingTourId: string | null;
  /** Tour whose SITL/connection launch gate is currently showing. */
  gateTourId: string | null;
  /** Tour whose panels/layout consent gate is currently showing. */
  panelGateTourId: string | null;

  markSeen: (id: string) => void;
  skipForSession: (id: string) => void;
  showPrompt: (id: string) => void;
  dismissPrompt: () => void;
  setActiveTour: (id: string | null) => void;
  setPendingTour: (id: string | null) => void;
  setGateTour: (id: string | null) => void;
  setPanelGateTour: (id: string | null) => void;
  resetAll: () => void;
}

export const useToursStore = create<ToursStore>((set) => ({
  seen: loadSeen(),
  skippedThisSession: new Set(),
  activeTourId: null,
  promptTourId: null,
  pendingTourId: null,
  gateTourId: null,
  panelGateTourId: null,

  markSeen: (id) =>
    set((state) => {
      const next = new Set(state.seen);
      next.add(id);
      persist(next);
      return { seen: next };
    }),

  skipForSession: (id) =>
    set((state) => {
      const next = new Set(state.skippedThisSession);
      next.add(id);
      return { skippedThisSession: next };
    }),

  showPrompt: (id) => set({ promptTourId: id }),
  dismissPrompt: () => set({ promptTourId: null }),
  setActiveTour: (id) => set({ activeTourId: id }),
  setPendingTour: (id) => set({ pendingTourId: id }),
  setGateTour: (id) => set({ gateTourId: id }),
  setPanelGateTour: (id) => set({ panelGateTourId: id }),

  resetAll: () => {
    persist(new Set());
    set({
      seen: new Set(),
      skippedThisSession: new Set(),
      pendingTourId: null,
      gateTourId: null,
      panelGateTourId: null,
    });
  },
}));

export function isTourEligible(id: string, state: ToursStore): boolean {
  return !state.seen.has(id) && !state.skippedThisSession.has(id);
}
