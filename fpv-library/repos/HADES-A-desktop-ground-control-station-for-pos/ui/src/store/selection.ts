import { create } from "zustand";

/* The global bidirectional selection spine (impl-plan Task 5.2 — BUILT FIRST; the
 * architectural spine, the Anduril-Lattice "one Contact, lit everywhere" lesson). One
 * Contact, three projections (map / list / video) over a SINGLE global selection: selecting
 * a contact anywhere selects it everywhere; map pin, list row, and video overlay all read
 * this one store.
 *
 * Two distinct kinds of "pointing at" a contact (DESIGN-SYSTEM §4.4 state matrix):
 *   - selectedId — the COMMITTED selection (a click). Drives the detail panel, framing, etc.
 *   - hoveredId  — a transient PREVIEW (a hover). Never alters the commit (hover ≠ commit).
 *
 * Crucially this store holds NO contact data — only ids. That independence is exactly why a
 * selection survives data updates / re-sorts: the data store can churn (new contacts, refined
 * records, re-sorts) without ever touching the selection here. Contacts are identified by
 * track_id (the stable cross-frame identity from the tracker). */

type TrackId = number;

interface SelectionState {
  selectedId: TrackId | null;
  hoveredId: TrackId | null;

  select: (id: TrackId) => void;
  toggle: (id: TrackId) => void;
  clear: () => void;
  hover: (id: TrackId) => void;
  clearHover: () => void;

  isSelected: (id: TrackId) => boolean;
  isHovered: (id: TrackId) => boolean;
  reset: () => void;
}

export const useSelectionStore = create<SelectionState>((set, get) => ({
  selectedId: null,
  hoveredId: null,

  select: (id) => set({ selectedId: id }),
  toggle: (id) => set((s) => ({ selectedId: s.selectedId === id ? null : id })),
  clear: () => set({ selectedId: null }),
  hover: (id) => set({ hoveredId: id }),
  clearHover: () => set({ hoveredId: null }),

  isSelected: (id) => get().selectedId === id,
  isHovered: (id) => get().hoveredId === id,
  reset: () => set({ selectedId: null, hoveredId: null }),
}));
