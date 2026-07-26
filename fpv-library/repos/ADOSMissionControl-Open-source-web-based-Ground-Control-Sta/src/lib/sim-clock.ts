/**
 * @module sim-clock
 * @description Pure, viewer-free math for the simulation playback clock.
 * The simulation store delegates time advancement to the CesiumJS clock and
 * stays in lockstep with it; these helpers hold the arithmetic (clamp, step,
 * seek, completion detection) so the timing rules are unit-testable without a
 * live 3D viewer. Quantization matches the precision the store syncs at.
 * @license GPL-3.0-only
 */

/** One step of the step-forward / step-back transport, in seconds. */
export const STEP_SECONDS = 1;

/** Playback rate options shared by the keyboard hook and the transport bar. */
export const PLAYBACK_SPEEDS = [0.25, 0.5, 1, 2, 4] as const;

/** Quantize elapsed seconds to milliseconds — matches the clock sync precision. */
export function quantizeElapsed(seconds: number): number {
  return Math.round(seconds * 1000) / 1000;
}

/** Clamp an elapsed time into [0, totalDuration] and quantize it. */
export function clampElapsed(seconds: number, totalDuration: number): number {
  const max = totalDuration > 0 ? totalDuration : 0;
  return quantizeElapsed(Math.max(0, Math.min(seconds, max)));
}

/** Next elapsed after a forward step, clamped to the end. */
export function stepForwardElapsed(elapsed: number, totalDuration: number): number {
  return clampElapsed(elapsed + STEP_SECONDS, totalDuration);
}

/** Next elapsed after a backward step, clamped to the start. */
export function stepBackElapsed(elapsed: number, totalDuration: number): number {
  return clampElapsed(elapsed - STEP_SECONDS, totalDuration);
}

/**
 * True when elapsed has reached (or passed) the end of a non-empty timeline.
 * A one-millisecond epsilon absorbs clock quantization so completion is not
 * missed by a sub-tick fraction.
 */
export function isAtEnd(elapsed: number, totalDuration: number): boolean {
  return totalDuration > 0 && elapsed >= totalDuration - 0.001;
}

/**
 * The elapsed value a freshly-retimed clock should resume at when the timeline
 * length changes. Preserves a non-zero position (re-clamped to the new length)
 * so changing the total duration never silently rewinds an in-progress preview.
 */
export function resumeElapsedForDuration(
  currentElapsed: number,
  totalDuration: number
): number {
  return clampElapsed(currentElapsed, totalDuration);
}
