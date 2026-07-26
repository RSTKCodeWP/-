/**
 * @module waypoint-clipboard
 * @description A tiny, module-level clipboard for planner waypoints. Copy stores
 * a snapshot of the selected waypoints here; paste reads them back. It lives
 * outside any store so the keyboard dispatcher and the planner page can share
 * one clipboard without a store round-trip, and so a copied set survives an
 * unrelated re-render.
 *
 * Every read and write deep-copies the waypoints, so a caller can freely mutate
 * what it copied in or reads out without corrupting the stored snapshot.
 *
 * Pure module state: no React, no store access.
 * @license GPL-3.0-only
 */

import type { Waypoint } from "@/lib/types/mission";

let clipboard: readonly Waypoint[] = [];

/** Replace the clipboard with a private copy of the given waypoints. */
export function setClipboard(waypoints: readonly Waypoint[]): void {
  clipboard = waypoints.map((wp) => ({ ...wp }));
}

/** Return a fresh copy of the clipboard contents (empty when nothing copied). */
export function getClipboard(): Waypoint[] {
  return clipboard.map((wp) => ({ ...wp }));
}

/** True when the clipboard holds at least one waypoint. */
export function hasClipboard(): boolean {
  return clipboard.length > 0;
}

/** Empty the clipboard. */
export function clearClipboard(): void {
  clipboard = [];
}
