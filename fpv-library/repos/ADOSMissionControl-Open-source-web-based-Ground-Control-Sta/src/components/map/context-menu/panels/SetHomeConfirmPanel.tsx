/**
 * @module map/context-menu/panels/SetHomeConfirmPanel
 * @description Set-home confirmation sub-panel inside the right-click menu.
 * Warns the operator that RTL and failsafe will use the new position.
 * @license GPL-3.0-only
 */

"use client";

interface SetHomeConfirmPanelProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export function SetHomeConfirmPanel({ onConfirm, onCancel }: SetHomeConfirmPanelProps) {
  return (
    <div className="px-3 py-2 border-b border-border-default">
      <div className="text-[10px] font-mono text-status-warning mb-1.5">Confirm: Set Home Here?</div>
      <div className="text-[9px] text-text-tertiary mb-2">
        This will change the home location. RTL and failsafe will use this new position.
      </div>
      <div className="flex gap-1">
        <button
          onClick={onConfirm}
          className="flex-1 px-2 py-1 text-[10px] font-mono font-semibold bg-status-warning/20 border border-status-warning/40 text-status-warning rounded hover:bg-status-warning/30 cursor-pointer"
        >
          Confirm
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
