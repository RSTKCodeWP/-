/**
 * Workspace store — renderer-side mirror of the detached windows currently
 * open. Used by:
 *   - Detachable wrapper: knows which panel is currently popped out (so the
 *     inline render switches to a placeholder).
 *   - Future "Window" menu / nav badge: shows a list of open pop-outs.
 *
 * The main process is the source of truth (window-manager.ts); this store
 * syncs from `onDetachedWindowOpened` / `onDetachedWindowClosed` push events
 * and a one-time `getDetachedWindows()` call on startup.
 */

import { create } from 'zustand';
import type { DetachedWindowInfo } from '../../shared/window-types';

interface WorkspaceState {
  /** Keyed by `id` (= componentId or componentId:instance). */
  windows: Record<string, DetachedWindowInfo>;
  /** True once initial sync has completed; UI can suppress flicker before this. */
  hydrated: boolean;

  setWindows: (list: DetachedWindowInfo[]) => void;
  addWindow: (info: DetachedWindowInfo) => void;
  removeWindow: (id: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  windows: {},
  hydrated: false,
  setWindows: (list) =>
    set({
      windows: Object.fromEntries(list.map((w) => [w.id, w])),
      hydrated: true,
    }),
  addWindow: (info) =>
    set((s) => ({ windows: { ...s.windows, [info.id]: info } })),
  removeWindow: (id) =>
    set((s) => {
      const next = { ...s.windows };
      delete next[id];
      return { windows: next };
    }),
}));

/**
 * Selector hook: returns true iff a detached window for the given component id
 * (and optional instance) is currently open. The Detachable wrapper uses this
 * to render the "open in window" placeholder instead of the panel content.
 */
export function useIsDetached(componentId: string, instance?: string): boolean {
  const id = instance ? `${componentId}:${instance}` : componentId;
  return useWorkspaceStore((s) => s.windows[id] !== undefined);
}

/**
 * Subscribe to main-process push events to keep `windows` in sync. Call once
 * per renderer process (main window only — detached windows don't need it
 * because they can't open further pop-outs in v1).
 */
export function setupWorkspaceSync(): () => void {
  const api = window.electronAPI;
  if (!api) return () => {};

  api.getDetachedWindows().then((list) => {
    useWorkspaceStore.getState().setWindows(list);
  }).catch(() => {
    // Main not ready yet — fine, the open/close events will populate us.
    useWorkspaceStore.setState({ hydrated: true });
  });

  const unsubOpen = api.onDetachedWindowOpened((info) => {
    useWorkspaceStore.getState().addWindow(info);
  });
  const unsubClose = api.onDetachedWindowClosed((id) => {
    useWorkspaceStore.getState().removeWindow(id);
  });

  return () => {
    unsubOpen?.();
    unsubClose?.();
  };
}
