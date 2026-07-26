/**
 * @module map/context-menu/panels/OrbitPanel
 * @description Orbit configuration sub-panel inside the right-click menu.
 * Operator picks radius and direction, then confirms.
 * @license GPL-3.0-only
 */

"use client";

interface OrbitPanelProps {
  radius: number;
  setRadius: (r: number) => void;
  clockwise: boolean;
  setClockwise: (cw: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function OrbitPanel({
  radius,
  setRadius,
  clockwise,
  setClockwise,
  onConfirm,
  onCancel,
}: OrbitPanelProps) {
  return (
    <div className="px-3 py-2 border-b border-border-default">
      <div className="text-[10px] font-mono text-text-secondary mb-1.5">Orbit Configuration</div>
      <div className="flex items-center gap-2 mb-1.5">
        <label className="text-[9px] text-text-tertiary w-12">Radius</label>
        <input
          type="number"
          value={radius}
          onChange={(e) => setRadius(Math.max(5, Math.min(500, Number(e.target.value))))}
          min={5}
          max={500}
          step={5}
          className="flex-1 px-1.5 py-0.5 text-[10px] font-mono bg-bg-tertiary border border-border-default rounded text-text-primary focus:border-accent-primary focus:outline-none"
        />
        <span className="text-[9px] text-text-tertiary">m</span>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <label className="text-[9px] text-text-tertiary w-12">Direction</label>
        <div className="flex gap-1">
          <button
            onClick={() => setClockwise(true)}
            className={`px-2 py-0.5 text-[9px] font-mono rounded border cursor-pointer ${
              clockwise
                ? "bg-accent-primary/20 border-accent-primary text-accent-primary"
                : "border-border-default text-text-tertiary"
            }`}
          >
            CW
          </button>
          <button
            onClick={() => setClockwise(false)}
            className={`px-2 py-0.5 text-[9px] font-mono rounded border cursor-pointer ${
              !clockwise
                ? "bg-accent-primary/20 border-accent-primary text-accent-primary"
                : "border-border-default text-text-tertiary"
            }`}
          >
            CCW
          </button>
        </div>
      </div>
      <div className="flex gap-1">
        <button
          onClick={onConfirm}
          className="flex-1 px-2 py-1 text-[10px] font-mono font-semibold bg-accent-primary/20 border border-accent-primary/40 text-accent-primary rounded hover:bg-accent-primary/30 cursor-pointer"
        >
          Start Orbit
        </button>
        <button
          onClick={onCancel}
          className="px-2 py-1 text-[10px] font-mono text-text-tertiary border border-border-default rounded hover:text-text-primary cursor-pointer"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
