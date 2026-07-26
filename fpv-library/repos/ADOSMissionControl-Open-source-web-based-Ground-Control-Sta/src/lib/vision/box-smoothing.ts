/**
 * @module vision/box-smoothing
 * @description Frame-rate-independent, critically-damped easing of a detection
 * bounding box toward a moving target. Offloaded detections arrive in bursts
 * (~10-15 batches/sec over a network round-trip), so a box that jumps straight
 * to each new position steps between batches and trails the subject. Easing the
 * on-screen box toward the latest detected box each animation frame makes it
 * glide and read as tracking.
 *
 * The model is first-order exponential smoothing: `alpha = 1 - exp(-dt / tau)`.
 * It is frame-rate independent (the same visual speed at 30 or 120 fps) and
 * never overshoots (each field moves monotonically from its current value
 * toward the target), which is the "critically-damped, no overshoot" property
 * we want for a target box.
 *
 * These are pure functions in frame-pixel space (the box's own resolution), so
 * they are independent of the rendered letterbox rect and are unit-testable
 * without a DOM.
 *
 * @license GPL-3.0-only
 */

import { clamp, lerp } from "@/lib/utils";

/** A pixel-space box `{x, y, width, height}`. Structurally compatible with the
 * detection store's `DetectionBox` so a raw detection box eases in place. */
export interface SmoothBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The interpolation fraction to move from the current value to the target this
 * step, given the elapsed time `dtMs` and the smoothing time-constant
 * `timeConstantMs` (roughly the time to close ~63% of the remaining gap).
 * Returns a value in `[0, 1]`: `0` when no time elapsed, approaching `1` for a
 * long gap or a zero/negative time-constant (snap).
 */
export function smoothingAlpha(dtMs: number, timeConstantMs: number): number {
  if (timeConstantMs <= 0) return 1;
  if (dtMs <= 0) return 0;
  return clamp(1 - Math.exp(-dtMs / timeConstantMs), 0, 1);
}

/**
 * Ease `current` toward `target` by the fraction `alpha` (from
 * {@link smoothingAlpha}), per field. With `alpha` in `[0, 1]` every field lands
 * between its current and target value, so the box never overshoots the target.
 */
export function easeBox(
  current: SmoothBox,
  target: SmoothBox,
  alpha: number,
): SmoothBox {
  return {
    x: lerp(current.x, target.x, alpha),
    y: lerp(current.y, target.y, alpha),
    width: lerp(current.width, target.width, alpha),
    height: lerp(current.height, target.height, alpha),
  };
}

/**
 * Largest per-field absolute difference between two boxes, in pixels. Used to
 * decide when a box has converged onto its target so the animation loop can
 * idle until the next detection batch arrives.
 */
export function boxDistance(a: SmoothBox, b: SmoothBox): number {
  return Math.max(
    Math.abs(a.x - b.x),
    Math.abs(a.y - b.y),
    Math.abs(a.width - b.width),
    Math.abs(a.height - b.height),
  );
}
