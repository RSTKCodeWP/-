/**
 * Detachable Windows (pop-out) — shared types.
 *
 * A "detachable component" is any renderer-side panel/view that can be hosted
 * either inline (inside the main window) or in its own OS-level BrowserWindow.
 * The componentId is the contract between main (which spawns the window) and
 * renderer (which renders the right thing for that id).
 *
 * New ids are added in renderer/detached/component-registry.ts; ids here are
 * left as `string` to avoid a coordinated edit every time a panel is wrapped.
 */

export interface DetachedWindowBounds {
  x?: number;
  y?: number;
  width: number;
  height: number;
}

/** Snapshot of an open detached window, sent main→renderer for badges / restore. */
export interface DetachedWindowInfo {
  /** Stable id (componentId + ':' + instance) used to address the window. */
  id: string;
  /** Which renderer component is hosted inside this window. */
  componentId: string;
  /** Optional instance suffix for multi-instance components (e.g. graphs). */
  instance?: string;
  /** Window title shown in the OS title bar. */
  title: string;
  /** Last-known bounds — written on move/resize so we can restore on next launch. */
  bounds: DetachedWindowBounds;
  /** Free-form component props (e.g. which field a graph is plotting). */
  props?: Record<string, unknown>;
}

/** Payload sent renderer→main to request opening a detached window. */
export interface OpenDetachedRequest {
  componentId: string;
  /** Optional instance suffix; required for multi-instance components. */
  instance?: string;
  title: string;
  initialBounds?: DetachedWindowBounds;
  props?: Record<string, unknown>;
}

/** Persisted workspace state — restored on app start. */
export interface WorkspaceStoreSchema {
  detachedWindows: DetachedWindowInfo[];
}
