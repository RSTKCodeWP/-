/**
 * Shared formation config + transient UI state for the fleet's RTS-style formation
 * controls. The glyph bar (FleetCoordination) and the right-click menu
 * (FleetContextMenu, on cards and map markers) both read/write here, so shape /
 * spacing / alt-step stay in sync across surfaces and a busy intent disables every
 * trigger at once. `contextMenu` holds the open right-click target.
 */

import { create } from 'zustand';

export interface FleetContextMenuState {
  x: number;
  y: number;
  vehicleKey: string;
}

interface FormationState {
  /** Active/last-applied formation shape (sent verbatim to the orchestrator). */
  shape: string;
  /** Metres between vehicles. */
  spacing: number;
  /** Altitude layer step (m) per rank. */
  altStep: number;
  /** An orchestration intent is in flight - disables every trigger. */
  busy: boolean;
  /** Open right-click menu target, or null. */
  contextMenu: FleetContextMenuState | null;
  setShape: (shape: string) => void;
  setSpacing: (spacing: number) => void;
  setAltStep: (altStep: number) => void;
  setBusy: (busy: boolean) => void;
  openContextMenu: (menu: FleetContextMenuState) => void;
  closeContextMenu: () => void;
}

export const useFormationStore = create<FormationState>((set) => ({
  shape: 'vee',
  spacing: 15,
  altStep: 5,
  busy: false,
  contextMenu: null,
  setShape: (shape) => set({ shape }),
  setSpacing: (spacing) => set({ spacing }),
  setAltStep: (altStep) => set({ altStep }),
  setBusy: (busy) => set({ busy }),
  openContextMenu: (contextMenu) => set({ contextMenu }),
  closeContextMenu: () => set({ contextMenu: null }),
}));
