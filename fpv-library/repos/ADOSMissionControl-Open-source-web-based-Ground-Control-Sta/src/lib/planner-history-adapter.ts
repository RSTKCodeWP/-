/**
 * @module planner-history-adapter
 * @description The mission-waypoint snapshot/restore adapter holder for the
 * coordinated planner undo timeline.
 *
 * This is a deliberately dependency-free leaf module. The coordinated history
 * (`planner-history.ts`) imports the three leaf domain stores, two of which pull
 * in the drone-manager graph; mission-store registers its adapter at module
 * init. If the holder lived in `planner-history.ts`, an import cycle re-entering
 * through that store graph could call `registerWaypointAdapter` while
 * `planner-history.ts` was still evaluating its own imports, before its
 * module-level `let` had initialised — a temporal-dead-zone throw. Isolating the
 * holder in a module that imports nothing means it is fully initialised before
 * any other module can reach it, so registration during a cycle is always safe.
 *
 * @license GPL-3.0-only
 */

/**
 * Opaque per-domain waypoint snapshot. The shape is owned by mission-store and
 * passed through the history untouched, so the history never has to know the
 * Waypoint type (which would create an import cycle).
 */
export type WaypointSnapshot = unknown;

/**
 * Adapter the mission-waypoint half registers so the coordinated history can
 * snapshot / restore waypoints without importing mission-store.
 */
export interface WaypointAdapter {
  snapshot: () => WaypointSnapshot;
  restore: (snap: WaypointSnapshot) => void;
}

let waypointAdapter: WaypointAdapter | null = null;

/**
 * Register the mission-waypoint snapshot/restore adapter. Called once by
 * mission-store at module init. Until registered, the waypoint half is a no-op
 * so the other three domains still undo/redo correctly (and tests that touch
 * only one domain do not have to wire mission-store).
 */
export function registerWaypointAdapter(adapter: WaypointAdapter): void {
  waypointAdapter = adapter;
}

/** Snapshot the registered waypoint domain, or `null` when none is registered. */
export function snapshotWaypoints(): WaypointSnapshot {
  return waypointAdapter ? waypointAdapter.snapshot() : null;
}

/** Restore the registered waypoint domain (no-op when none is registered). */
export function restoreWaypoints(snap: WaypointSnapshot): void {
  if (waypointAdapter) waypointAdapter.restore(snap);
}
