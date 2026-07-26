/**
 * @module changelog-notification-store
 * @description Volatile Zustand store for changelog notification state.
 * NOT persisted — lives only for the current session. Bridges the Convex gate
 * (which knows unseen count) with the header badge (which always renders).
 * @license GPL-3.0-only
 */

import { create } from "zustand";

interface ChangelogNotificationState {
  unseenCount: number;
  modalOpen: boolean;
  setUnseenCount: (count: number) => void;
  setModalOpen: (open: boolean) => void;
}

export const useChangelogNotificationStore = create<ChangelogNotificationState>()(
  (set) => ({
    unseenCount: 0,
    modalOpen: false,
    setUnseenCount: (unseenCount) => set({ unseenCount }),
    setModalOpen: (modalOpen) => set({ modalOpen }),
  })
);
