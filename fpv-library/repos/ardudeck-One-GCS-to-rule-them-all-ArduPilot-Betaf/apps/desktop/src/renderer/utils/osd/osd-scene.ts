/**
 * Shared "FPV scene" backdrop for OSD previews - a sky/ground horizon gradient
 * so an OSD/HUD is previewed over a representative video view rather than a flat
 * card. Used by the HUD, Text OSD and RubyFPV previews. License-clean (our own
 * gradient, no third-party asset).
 */

/** Gradient colour stops: [offset 0..1, css colour]. */
export const SCENE_STOPS: [number, string][] = [
  [0, '#40617d'],
  [0.46, '#5e7f9e'],
  [0.54, '#7d8a6a'],
  [1, '#46503a'],
];

/** CSS `background` value for DOM elements. */
export const FPV_SCENE_BG = `linear-gradient(to bottom, ${SCENE_STOPS.map(([o, c]) => `${c} ${Math.round(o * 100)}%`).join(', ')})`;

/** Build the same scene as a vertical canvas gradient (for 2D contexts). */
export function sceneCanvasGradient(ctx: CanvasRenderingContext2D, height: number): CanvasGradient {
  const g = ctx.createLinearGradient(0, 0, 0, height);
  for (const [o, c] of SCENE_STOPS) g.addColorStop(o, c);
  return g;
}
