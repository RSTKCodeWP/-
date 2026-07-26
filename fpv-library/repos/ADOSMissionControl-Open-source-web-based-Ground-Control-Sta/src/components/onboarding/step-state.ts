/**
 * Pure helpers for the WelcomeModal step state machine.
 *
 * Kept as a tiny standalone module so the math is unit-testable without a
 * full React render. The component imports from here.
 *
 * @license GPL-3.0-only
 */

export type Step = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type StepDirection = "forward" | "back";

/**
 * Tailwind translate class for a given step pane.
 *
 * - The active pane sits at translate-x-0 (centred).
 * - Past panes slide off to the left when moving forward, to the right when moving back.
 * - Future panes wait off to the right when moving forward, to the left when moving back.
 *
 * The values are static Tailwind class names so JIT can pre-generate them.
 */
export function computeStepX(i: Step, current: Step, direction: StepDirection): string {
  if (i === current) return "translate-x-0";
  if (i < current) return direction === "forward" ? "-translate-x-full" : "translate-x-full";
  return direction === "forward" ? "translate-x-full" : "-translate-x-full";
}

/**
 * Index used by the step-dots indicator. When the desktop download step is
 * skipped (Electron build), the steps after it collapse back by one
 * position so the dot count stays aligned with the visible flow. Download
 * sits at index 6.
 */
export function computeDotStep(step: Step, skipDownloadStep: boolean): number {
  return skipDownloadStep && step > 6 ? step - 1 : step;
}

export function computeTotalSteps(skipDownloadStep: boolean): number {
  return skipDownloadStep ? 7 : 8;
}

export function computeAfterTheme(skipDownloadStep: boolean): Step {
  return skipDownloadStep ? 7 : 6;
}

export function computeBeforeReady(skipDownloadStep: boolean): Step {
  return skipDownloadStep ? 5 : 6;
}
