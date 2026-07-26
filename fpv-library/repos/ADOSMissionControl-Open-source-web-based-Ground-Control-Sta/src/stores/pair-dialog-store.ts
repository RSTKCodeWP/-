/**
 * @module pair-dialog-store
 * @description Global open/close state for the Pair-a-Node dialog, mirroring
 * connect-dialog-store. Lifting this out of CommandPage's local state lets the
 * dashboard zero-state and the locked agent tabs open pairing from anywhere
 * without prop-drilling. CommandPage still owns the PairingDialog mount and the
 * `/pair?code=` deep-link continues to drive the initial code independently.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

/** Which tab the pairing dialog should open on. */
export type PairDialogTab = "add" | "generate";

interface PairDialogState {
  open: boolean;
  /** Preferred tab when the dialog opens. Consumers may ignore it. */
  initialTab: PairDialogTab;
  openDialog: (initialTab?: PairDialogTab) => void;
  closeDialog: () => void;
}

export const usePairDialogStore = create<PairDialogState>((set) => ({
  open: false,
  initialTab: "add",
  openDialog: (initialTab: PairDialogTab = "add") => set({ open: true, initialTab }),
  closeDialog: () => set({ open: false }),
}));
