/**
 * Position of the free-floating fleet minimap (viewport pixel coords of its top-left).
 * `setPos` updates in memory (cheap, called every drag frame); `persist` writes the
 * current position to localStorage (called once, on drop). Null until first placed; the
 * widget then defaults to the lower-right.
 */

import { create } from 'zustand';

const KEY = 'ardudeck.minimapPos';

function load(): { x: number | null; y: number | null } {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw);
      if (typeof p.x === 'number' && typeof p.y === 'number') return p;
    }
  } catch { /* ignore */ }
  return { x: null, y: null };
}

interface State {
  x: number | null;
  y: number | null;
  setPos: (x: number, y: number) => void;
  persist: () => void;
}

export const useMinimapStore = create<State>((set, get) => ({
  ...load(),
  setPos: (x, y) => set({ x, y }),
  persist: () => {
    const { x, y } = get();
    try { localStorage.setItem(KEY, JSON.stringify({ x, y })); } catch { /* ignore */ }
  },
}));
