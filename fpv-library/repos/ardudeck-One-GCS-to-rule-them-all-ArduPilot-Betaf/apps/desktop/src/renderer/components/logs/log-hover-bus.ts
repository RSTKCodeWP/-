// Tiny pub/sub for cross-panel time coordination in the log explorer.
// Deliberately NOT zustand: hover fires on every mousemove and a store write
// would re-render every subscribed component per frame. Panels that care
// subscribe imperatively (uPlot instances, maplibre markers) and mutate their
// own canvas/DOM without touching React state.

export type TimeRange = { min: number; max: number };

type HoverListener = (timeS: number | null) => void;
type JumpListener = (range: TimeRange) => void;

const hoverListeners = new Set<HoverListener>();
const jumpListeners = new Set<JumpListener>();

/** Cursor time under the mouse on any chart; null = mouse left the plot. */
export function publishHoverTime(timeS: number | null): void {
  for (const l of hoverListeners) l(timeS);
}

export function subscribeHoverTime(fn: HoverListener): () => void {
  hoverListeners.add(fn);
  return () => { hoverListeners.delete(fn); };
}

/** Ask every chart to jump its X window (e.g. "show me this error moment"). */
export function publishTimeJump(range: TimeRange): void {
  for (const l of jumpListeners) l(range);
}

export function subscribeTimeJump(fn: JumpListener): () => void {
  jumpListeners.add(fn);
  return () => { jumpListeners.delete(fn); };
}
