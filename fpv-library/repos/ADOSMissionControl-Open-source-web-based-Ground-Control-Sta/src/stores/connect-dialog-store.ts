/**
 * @module connect-dialog-store
 * @description Global state for the connect dialog open/close.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

interface ConnectDialogState {
  open: boolean;
  openDialog: () => void;
  closeDialog: () => void;
}

export const useConnectDialogStore = create<ConnectDialogState>((set) => ({
  open: false,
  openDialog: () => set({ open: true }),
  closeDialog: () => set({ open: false }),
}));
