/**
 * Step indicator dots shown beneath every onboarding pane.
 *
 * @license GPL-3.0-only
 */

"use client";

interface StepDotsProps {
  step: number;
  total: number;
}

export function StepDots({ step, total }: StepDotsProps) {
  return (
    <div className="flex gap-2 justify-center mt-8">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`w-2 h-2 rounded-full transition-colors duration-300 ${
            i <= step ? "bg-accent-primary" : "bg-bg-tertiary"
          }`}
        />
      ))}
    </div>
  );
}
