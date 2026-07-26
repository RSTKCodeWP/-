"use client";

/**
 * @module use-has-mounted
 * @description Returns `false` on the server and on the client's first
 * (hydration) render, then `true` after the component mounts. Use it to gate
 * client-only content that would otherwise diverge from the server-rendered
 * HTML — most notably anything derived from `isDemoMode()`, whose `?demo=true`
 * URL branch only exists on the client (see `src/lib/utils.ts`). Rendering that
 * content during the first client pass makes React's hydration comparison fail
 * (minified error #418); deferring it to `useHasMounted() === true` keeps the
 * first client render byte-identical to the SSR output and reveals the content
 * one tick later.
 *
 * @license GPL-3.0-only
 */

import { useSyncExternalStore } from "react";

/** No external source to watch — the snapshot never changes after mount. */
const subscribe = (): (() => void) => () => {};

export function useHasMounted(): boolean {
  // `useSyncExternalStore` uses the server snapshot (`false`) for SSR and the
  // first client (hydration) render, then the client snapshot (`true`) once
  // mounted — the React-blessed hydration-safe client flag, with no
  // setState-in-effect cascade.
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
