/**
 * Pure-function tests for the WelcomeModal step state machine.
 *
 * Covers the slide-direction calculator, the dot-step indicator remap, and
 * the step constants that change when the desktop download step is skipped
 * (Electron build).
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  computeStepX,
  computeDotStep,
  computeTotalSteps,
  computeAfterTheme,
  computeBeforeReady,
} from "@/components/onboarding/step-state";

describe("computeStepX", () => {
  it("returns translate-x-0 for the active pane regardless of direction", () => {
    expect(computeStepX(2, 2, "forward")).toBe("translate-x-0");
    expect(computeStepX(2, 2, "back")).toBe("translate-x-0");
  });

  it("slides past panes off to the left when moving forward", () => {
    expect(computeStepX(0, 2, "forward")).toBe("-translate-x-full");
    expect(computeStepX(1, 2, "forward")).toBe("-translate-x-full");
  });

  it("slides past panes off to the right when moving back", () => {
    expect(computeStepX(0, 2, "back")).toBe("translate-x-full");
    expect(computeStepX(1, 2, "back")).toBe("translate-x-full");
  });

  it("parks future panes off to the right when moving forward", () => {
    expect(computeStepX(3, 2, "forward")).toBe("translate-x-full");
    expect(computeStepX(6, 2, "forward")).toBe("translate-x-full");
  });

  it("parks future panes off to the left when moving back", () => {
    expect(computeStepX(3, 2, "back")).toBe("-translate-x-full");
    expect(computeStepX(6, 2, "back")).toBe("-translate-x-full");
  });
});

describe("computeDotStep", () => {
  it("passes the step through unchanged when the download step is shown", () => {
    expect(computeDotStep(0, false)).toBe(0);
    expect(computeDotStep(3, false)).toBe(3);
    expect(computeDotStep(5, false)).toBe(5);
    expect(computeDotStep(6, false)).toBe(6);
  });

  it("collapses step 7 down to dot index 6 when the download step is skipped", () => {
    expect(computeDotStep(7, true)).toBe(6);
  });

  it("does not remap steps at or below the download step when it is skipped", () => {
    expect(computeDotStep(0, true)).toBe(0);
    expect(computeDotStep(5, true)).toBe(5);
    expect(computeDotStep(6, true)).toBe(6);
  });
});

describe("computeTotalSteps", () => {
  it("returns 8 in browser mode", () => {
    expect(computeTotalSteps(false)).toBe(8);
  });

  it("returns 7 in Electron mode (no desktop download step)", () => {
    expect(computeTotalSteps(true)).toBe(7);
  });
});

describe("computeAfterTheme and computeBeforeReady", () => {
  it("targets step 6 (download) after theme in browser mode", () => {
    expect(computeAfterTheme(false)).toBe(6);
  });

  it("targets step 7 (ready) after theme in Electron mode", () => {
    expect(computeAfterTheme(true)).toBe(7);
  });

  it("backs from ready into the download step in browser mode", () => {
    expect(computeBeforeReady(false)).toBe(6);
  });

  it("backs from ready into the theme step in Electron mode", () => {
    expect(computeBeforeReady(true)).toBe(5);
  });
});
