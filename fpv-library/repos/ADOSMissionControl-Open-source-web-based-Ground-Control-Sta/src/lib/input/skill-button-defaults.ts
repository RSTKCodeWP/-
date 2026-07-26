/**
 * The documented default gamepad button -> skill map. A standard controller's
 * face buttons map to the four most common one-shot flight skills so a fresh
 * loadout is button-drivable out of the box, and "Apply controller defaults"
 * can re-seed these onto the active loadout's matching slots.
 *
 *   A (0) -> arm     B (1) -> rth     X (2) -> land     Y (3) -> pause
 *
 * Axes (roll/pitch/throttle/yaw) come from the gamepad-poller's stick mapping,
 * never from this table — there is no index overlap, so a button binding can
 * never collide with a stick axis.
 *
 * @module input/skill-button-defaults
 * @license GPL-3.0-only
 */

export interface SkillButtonDefault {
  skillId: string;
  button: number;
}

/** Default face-button bindings, mirroring the factory default loadout. */
export const SKILL_BUTTON_DEFAULTS: readonly SkillButtonDefault[] = [
  { skillId: "arm", button: 0 },
  { skillId: "rth", button: 1 },
  { skillId: "land", button: 2 },
  { skillId: "pause", button: 3 },
];
