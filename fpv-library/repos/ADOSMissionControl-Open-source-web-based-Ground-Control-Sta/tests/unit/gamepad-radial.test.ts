/**
 * Tests for the gamepad radial selection geometry: mapping a screen-direction
 * angle (0 = up, clockwise) to the nearest wedge index. The wire from d-pad /
 * right-stick aim to a highlighted skill rides entirely on this function.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  nearestWedge,
  RADIAL_GAMEPAD_BUTTON,
  type RadialWedge,
} from "@/hooks/use-gamepad-radial";
import type { Skill } from "@/lib/skills/types";

function fakeSkill(id: string): Skill {
  return {
    id,
    label: id,
    icon: "Sparkles",
    category: "flight",
    source: "builtin",
    toggle: false,
    getState: () => ({ kind: "idle" }),
    activate: async () => {},
  };
}

/** Build N evenly-spaced wedges (0 = up, clockwise) like the hook does. */
function wedges(n: number): RadialWedge[] {
  return Array.from({ length: n }, (_, i) => ({
    skill: fakeSkill(`s${i}`),
    angle: (i / n) * 2 * Math.PI,
  }));
}

describe("nearestWedge", () => {
  it("returns -1 when there are no wedges", () => {
    expect(nearestWedge([], 0)).toBe(-1);
  });

  it("maps the up direction to the first (top) wedge", () => {
    expect(nearestWedge(wedges(4), 0)).toBe(0);
  });

  it("maps the right direction to the right (quarter) wedge", () => {
    // 4 wedges at 0, 90, 180, 270 deg -> right = 90 deg = index 1.
    expect(nearestWedge(wedges(4), Math.PI / 2)).toBe(1);
  });

  it("maps the down direction to the bottom wedge", () => {
    expect(nearestWedge(wedges(4), Math.PI)).toBe(2);
  });

  it("maps the left direction to the left wedge", () => {
    expect(nearestWedge(wedges(4), (3 * Math.PI) / 2)).toBe(3);
  });

  it("wraps across the 0/2pi seam (just-shy-of-up snaps to top)", () => {
    // 2pi - epsilon is nearer to wedge 0 (at 0) than any other wedge.
    expect(nearestWedge(wedges(4), 2 * Math.PI - 0.05)).toBe(0);
  });

  it("snaps an off-axis aim to the closest wedge", () => {
    // 80 deg is closer to the 90-deg wedge (index 1) than the 0-deg wedge.
    expect(nearestWedge(wedges(4), (80 * Math.PI) / 180)).toBe(1);
  });

  it("handles a single wedge by always selecting it", () => {
    expect(nearestWedge(wedges(1), Math.PI)).toBe(0);
    expect(nearestWedge(wedges(1), 0)).toBe(0);
  });

  it("reserves a hold button that does not collide with the exit chord", () => {
    // The cockpit exit chord is gamepad button 9 (Start); the radial must not
    // share it.
    expect(RADIAL_GAMEPAD_BUTTON).not.toBe(9);
  });
});
