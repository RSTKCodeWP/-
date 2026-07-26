/**
 * @module use-prefers-reduced-motion
 * @description Reactively tracks the `prefers-reduced-motion: reduce` media
 * query so a component can swap a continuously-animating affordance (a sweeping
 * cooldown arc, a transient radial overlay) for a static one. SSR-safe via
 * useSyncExternalStore: the server snapshot is false, the client reads the live
 * media query and re-renders on change.
 *
 * @license GPL-3.0-only
 */

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const mql = window.matchMedia(QUERY);
  mql.addEventListener("change", onChange);
  return () => mql.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

/** Server snapshot: no motion preference is known until the client mounts. */
function getServerSnapshot(): boolean {
  return false;
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
