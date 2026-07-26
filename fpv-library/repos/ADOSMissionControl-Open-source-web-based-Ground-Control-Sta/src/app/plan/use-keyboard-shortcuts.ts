/**
 * @module use-keyboard-shortcuts
 * @description The single, ordered keyboard dispatcher for the mission planner.
 *
 * This hook is the ONLY keyboard owner for the planner. The drawing manager no
 * longer registers its own document listeners; instead this dispatcher reaches
 * the active draw through {@link getActiveDrawApi} and calls its imperative
 * methods. Having one ordered owner removes the old race where a planner hook and
 * the drawing manager both listened on `document` and fought over Escape /
 * Backspace.
 *
 * Precedence is deliberate and fixed:
 *   1. Typing-target guard — never hijack a key while the user types in a field.
 *   2. Tool / panel letter shortcuts (no modifier), plus arrow-key nudge of the
 *      selected waypoint.
 *   3. Undo / redo (Cmd/Ctrl+Z), then copy / paste (Cmd/Ctrl+C / V) of the
 *      selected waypoint(s) — copy defers to a live page text selection.
 *   4. Escape — cancel the active draw first, else collapse an expanded waypoint,
 *      else clear any non-select tool back to select.
 *   5. Backspace / Delete — pop a draw vertex while drawing, else delete the
 *      selected waypoint.
 *   6. Save / Save-As (Cmd/Ctrl+S).
 *   7. New / Open accelerator chords — desktop (Electron) only, so the browser
 *      keeps its native Cmd/Ctrl+N / Cmd/Ctrl+O behaviour.
 *
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import type { PlannerTool } from "@/lib/types";
import { isTypingTarget, isElectron } from "@/lib/utils";
import { getActiveDrawApi } from "@/lib/drawing/drawing-manager";
import { TOOL_SHORTCUT_MAP } from "@/lib/planner-shortcuts";

interface UseKeyboardShortcutsParams {
  activeTool: PlannerTool;
  setActiveTool: (tool: PlannerTool) => void;
  undo: () => void;
  redo: () => void;
  selectedWaypointId: string | null;
  removeWaypoint: (id: string) => void;
  setSelectedWaypoint: (id: string | null) => void;
  expandedWaypointId: string | null;
  setExpandedWaypoint: (id: string | null) => void;
  handleSave: () => void;
  handleSaveAs?: () => void;
  handleNewPlan?: () => void;
  handleFocusSearch?: () => void;
  onTogglePatternEditor?: () => void;
  onToggleValidation?: () => void;
  onToggleTerrain?: () => void;
  onToggleOverlays?: () => void;
  onFocusPlaceSearch?: () => void;
  /**
   * Nudge the selected waypoint by a small offset. An arrow key moves a fine
   * step; Shift+arrow a coarser one. dLat is positive north, dLon positive east.
   */
  onNudgeSelected?: (dLat: number, dLon: number) => void;
  /** Copy the selected waypoint(s) to the shared waypoint clipboard. */
  onCopy?: () => void;
  /** Paste the waypoint clipboard back into the plan, offset slightly. */
  onPaste?: () => void;
}

/** Fine nudge step for a plain arrow key, in degrees (~1.1 m near the equator). */
const NUDGE_STEP_FINE = 1e-5;
/** Coarser nudge step when Shift is held, in degrees. */
const NUDGE_STEP_COARSE = 1e-4;

/**
 * Tool-select letter shortcuts, derived from the single {@link PLANNER_SHORTCUTS}
 * table so the dispatched keys, the on-map help popover, and the command palette
 * can never drift apart. Each plain letter maps to exactly one tool; the
 * panel/overlay letters (T / G / I / L) below use a disjoint set.
 */
const TOOL_MAP: Readonly<Record<string, PlannerTool>> = TOOL_SHORTCUT_MAP;

/** True for the tools whose map gesture is an in-progress shape draw. */
function isDrawingTool(tool: PlannerTool): boolean {
  return tool === "polygon" || tool === "circle" || tool === "measure";
}

/** Register the single global keyboard dispatcher for the mission planner. */
export function useKeyboardShortcuts({
  activeTool,
  setActiveTool,
  undo,
  redo,
  selectedWaypointId,
  removeWaypoint,
  setSelectedWaypoint,
  expandedWaypointId,
  setExpandedWaypoint,
  handleSave,
  handleSaveAs,
  handleNewPlan,
  handleFocusSearch,
  onTogglePatternEditor,
  onToggleValidation,
  onToggleTerrain,
  onToggleOverlays,
  onFocusPlaceSearch,
  onNudgeSelected,
  onCopy,
  onPaste,
}: UseKeyboardShortcutsParams): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 1. Typing-target guard — a key pressed inside an input/textarea/select or
      // a contenteditable surface is never a planner shortcut.
      if (isTypingTarget(e.target)) return;

      const isMeta = e.metaKey || e.ctrlKey;
      const draw = getActiveDrawApi();
      // The store-driven tool says a drawing tool is selected; the manager API
      // says a draw is actually in progress. Prefer the live manager state when
      // present and fall back to the tool when no manager is registered (tests,
      // SSR, transient unmount), so Backspace/Escape stay correct either way.
      const drawing = draw ? draw.isDrawing() : isDrawingTool(activeTool);

      // 2. Tool + panel letter shortcuts (no modifier).
      if (!isMeta) {
        const tool = TOOL_MAP[e.key.toLowerCase()];
        if (tool) {
          e.preventDefault();
          setActiveTool(tool);
          return;
        }

        if (e.key.toLowerCase() === "t") {
          e.preventDefault();
          onToggleTerrain?.();
          return;
        }
        if (e.key.toLowerCase() === "g") {
          e.preventDefault();
          onTogglePatternEditor?.();
          return;
        }
        if (e.key.toLowerCase() === "i") {
          e.preventDefault();
          onToggleValidation?.();
          return;
        }
        if (e.key.toLowerCase() === "l") {
          e.preventDefault();
          onToggleOverlays?.();
          return;
        }
        if (e.key === "/") {
          e.preventDefault();
          onFocusPlaceSearch?.();
          return;
        }

        // Arrow keys nudge the selected waypoint by a small step (coarser with
        // Shift). Only handled when a waypoint is selected and the page supplied
        // a nudge handler, so an arrow with no selection keeps native scrolling.
        if (onNudgeSelected && selectedWaypointId) {
          const step = e.shiftKey ? NUDGE_STEP_COARSE : NUDGE_STEP_FINE;
          if (e.key === "ArrowUp") {
            e.preventDefault();
            onNudgeSelected(step, 0);
            return;
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            onNudgeSelected(-step, 0);
            return;
          }
          if (e.key === "ArrowLeft") {
            e.preventDefault();
            onNudgeSelected(0, -step);
            return;
          }
          if (e.key === "ArrowRight") {
            e.preventDefault();
            onNudgeSelected(0, step);
            return;
          }
        }
      }

      // 3. Undo / redo.
      if (isMeta && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
        return;
      }
      if (isMeta && e.key === "z" && e.shiftKey) {
        e.preventDefault();
        redo();
        return;
      }

      // 3b. Copy / paste of the selected waypoint(s). Never hijack a real text
      // selection: if the user has text highlighted on the page, leave the
      // browser's native copy alone. (Typing targets are already handled above.)
      if (isMeta && e.key.toLowerCase() === "c") {
        if (!onCopy) return;
        const selection = typeof window !== "undefined" ? window.getSelection?.() : null;
        if (selection && selection.toString().length > 0) return;
        e.preventDefault();
        onCopy();
        return;
      }
      if (isMeta && e.key.toLowerCase() === "v") {
        if (!onPaste) return;
        e.preventDefault();
        onPaste();
        return;
      }

      // 4. Escape — drawing-cancel takes precedence over the generic clear.
      if (e.key === "Escape") {
        e.preventDefault();
        if (drawing) {
          // Cancel the active draw via the manager, then return the tool to
          // select. The manager's onCancel callback clears the drawing store.
          draw?.cancel();
          setActiveTool("select");
          return;
        }
        if (expandedWaypointId) {
          setExpandedWaypoint(null);
        } else if (activeTool !== "select") {
          setActiveTool("select");
        }
        return;
      }

      // 5. Backspace / Delete — vertex-pop while drawing wins over waypoint-delete.
      if (e.key === "Backspace" || e.key === "Delete") {
        if (drawing) {
          // Only Backspace pops a vertex; Delete is ignored while drawing so it
          // can never also remove a still-selected waypoint mid-draw.
          if (e.key === "Backspace") {
            e.preventDefault();
            draw?.popVertex();
          }
          return;
        }
        if (selectedWaypointId) {
          e.preventDefault();
          removeWaypoint(selectedWaypointId);
          setSelectedWaypoint(null);
          setExpandedWaypoint(null);
          return;
        }
      }

      // 6. Save / Save-As.
      if (isMeta && e.key === "s" && e.shiftKey) {
        e.preventDefault();
        handleSaveAs?.();
        return;
      }
      if (isMeta && e.key === "s" && !e.shiftKey) {
        e.preventDefault();
        handleSave();
        return;
      }

      // 7. New / Open accelerator chords — desktop only. In the browser these
      // are native chords (new window / open file) and must not be hijacked.
      if (isMeta && e.key === "n") {
        if (!isElectron()) return;
        e.preventDefault();
        handleNewPlan?.();
        return;
      }
      if (isMeta && e.key === "o") {
        if (!isElectron()) return;
        e.preventDefault();
        handleFocusSearch?.();
        return;
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [
    activeTool,
    setActiveTool,
    undo,
    redo,
    selectedWaypointId,
    removeWaypoint,
    setSelectedWaypoint,
    expandedWaypointId,
    setExpandedWaypoint,
    handleSave,
    handleSaveAs,
    handleNewPlan,
    handleFocusSearch,
    onTogglePatternEditor,
    onToggleValidation,
    onToggleTerrain,
    onToggleOverlays,
    onFocusPlaceSearch,
    onNudgeSelected,
    onCopy,
    onPaste,
  ]);
}
