/**
 * @module planner-commands
 * @description Builds the mission-planner command-palette verbs from the single
 * PLANNER_SHORTCUTS table, so every planner action reachable by a shortcut is
 * also reachable from ⌘K. Registered by the planner page while it is mounted.
 * @license GPL-3.0-only
 */

import type { PaletteCommand } from "@/lib/command-palette-registry";
import type { PlannerTool } from "@/lib/types";
import { PLANNER_SHORTCUTS } from "@/lib/planner-shortcuts";

/** The planner handlers a command needs to invoke. */
export interface PlannerCommandHandlers {
  setActiveTool: (tool: PlannerTool) => void;
  undo: () => void;
  redo: () => void;
  handleSave: () => void;
  handleSaveAs?: () => void;
  handleNewPlan?: () => void;
  toggleTerrain: () => void;
  togglePattern: () => void;
  toggleValidation: () => void;
  toggleOverlays: () => void;
}

/**
 * Map a shortcut to the planner handler it invokes, or null when the shortcut is
 * context-dependent (delete/cancel act on the current selection/draw and have no
 * standalone palette verb).
 */
function actionFor(labelKey: string, h: PlannerCommandHandlers): (() => void) | null {
  const s = PLANNER_SHORTCUTS.find((x) => x.labelKey === labelKey);
  if (!s) return null;
  if (s.group === "tool" && s.tool) return () => h.setActiveTool(s.tool!);
  switch (labelKey) {
    case "shortcuts.terrain": return h.toggleTerrain;
    case "shortcuts.patterns": return h.togglePattern;
    case "shortcuts.validation": return h.toggleValidation;
    case "shortcuts.overlays": return h.toggleOverlays;
    case "shortcuts.undo": return h.undo;
    case "shortcuts.redo": return h.redo;
    case "shortcuts.save": return h.handleSave;
    case "shortcuts.saveAs": return h.handleSaveAs ?? null;
    case "shortcuts.newPlan": return h.handleNewPlan ?? null;
    default: return null; // delete / cancel are selection/draw-scoped
  }
}

/**
 * Build the planner palette commands. `label(labelKey)` and `category` are the
 * already-translated strings supplied by the caller; `query` filters by label
 * (the palette does not re-filter provider results).
 */
export function buildPlannerCommands(
  h: PlannerCommandHandlers,
  label: (labelKey: string) => string,
  category: string,
  query: string,
): PaletteCommand[] {
  const q = query.trim().toLowerCase();
  const cmds: PaletteCommand[] = [];
  for (const s of PLANNER_SHORTCUTS) {
    const action = actionFor(s.labelKey, h);
    if (!action) continue;
    const text = label(s.labelKey);
    if (q && !text.toLowerCase().includes(q)) continue;
    cmds.push({ id: `planner-${s.labelKey}`, label: text, category, action });
  }
  return cmds;
}
