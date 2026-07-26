/**
 * @module auth-store
 * @description Zustand store for authentication state.
 * Tracks whether the user is signed in, their profile, and sync status.
 * Auth is entirely optional — the app works fully without it.
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
}

export type SyncStatus = "idle" | "syncing" | "synced" | "error" | "offline";

interface AuthStoreState {
  /** Whether the user is authenticated. */
  isAuthenticated: boolean;
  /** Whether auth state is still loading. */
  isLoading: boolean;
  /** The authenticated user, or null. */
  user: AuthUser | null;
  /** Whether cloud sync is enabled (requires auth). */
  syncEnabled: boolean;
  /** Current sync status. */
  syncStatus: SyncStatus;
  /** Timestamp of last successful sync. */
  lastSyncedAt: number | null;

  setAuth: (user: AuthUser | null) => void;
  setLoading: (loading: boolean) => void;
  setSyncEnabled: (enabled: boolean) => void;
  setSyncStatus: (status: SyncStatus) => void;
  setLastSyncedAt: (timestamp: number | null) => void;
  signOut: () => void;
}

export const useAuthStore = create<AuthStoreState>((set) => ({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  syncEnabled: false,
  syncStatus: "idle",
  lastSyncedAt: null,

  setAuth: (user) =>
    set({
      user,
      isAuthenticated: user !== null,
      isLoading: false,
      syncEnabled: user !== null,
    }),
  setLoading: (isLoading) => set({ isLoading }),
  setSyncEnabled: (syncEnabled) => set({ syncEnabled }),
  setSyncStatus: (syncStatus) => set({ syncStatus }),
  setLastSyncedAt: (lastSyncedAt) => set({ lastSyncedAt }),
  signOut: () =>
    set({
      user: null,
      isAuthenticated: false,
      syncEnabled: false,
      syncStatus: "idle",
      lastSyncedAt: null,
    }),
}));
