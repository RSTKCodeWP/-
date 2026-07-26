/**
 * @module cockpit/density
 * @description The cockpit information-density model. A density mode gates how
 * much read-only chrome the immersive cockpit shows: `minimal` hides the
 * `.d-std` + `.d-full` cards, `standard` hides only `.d-full`, and `full` shows
 * everything (see the `[data-density=…]` rules in globals.css). Kept in one
 * dependency-free module so both the density control and the persisted loadout
 * layout reference the same type + default without a component ⇄ store import.
 *
 * @license GPL-3.0-only
 */

/** How dense the cockpit read-outs are: fewer cards → more video. */
export type CockpitDensity = "minimal" | "standard" | "full";

/** The density modes in display order (Min · Std · Full). */
export const COCKPIT_DENSITIES: readonly CockpitDensity[] = [
  "minimal",
  "standard",
  "full",
];

/** The factory density: a balanced set of cards over the video. */
export const DEFAULT_DENSITY: CockpitDensity = "standard";

/** Narrow an untrusted value (a persisted setting) to a known density mode. */
export function isCockpitDensity(value: unknown): value is CockpitDensity {
  return (
    value === "minimal" || value === "standard" || value === "full"
  );
}
