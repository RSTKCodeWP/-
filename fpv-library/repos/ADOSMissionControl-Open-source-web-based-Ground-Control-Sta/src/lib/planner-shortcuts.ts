/**
 * @module planner-shortcuts
 * @description The single source of truth for the mission planner's keyboard
 * shortcuts. The on-map help popover, the keyboard dispatcher, and the command
 * palette all read this one table, so the advertised keys, the dispatched keys,
 * and the palette verbs can never drift apart.
 *
 * Pure data module: no React, no store access.
 * @license GPL-3.0-only
 */

import type { PlannerTool } from "@/lib/types";

/** How a shortcut is grouped in the help popover and the palette. */
export type PlannerShortcutGroup = "tool" | "panel" | "overlay" | "edit" | "file";

export interface PlannerShortcut {
  /** The lowercase letter, or a chord/key label shown to the user (e.g. "Del"). */
  readonly key: string;
  /** A translatable description key, relative to the `planner` namespace. */
  readonly labelKey: string;
  /** The group this shortcut belongs to. */
  readonly group: PlannerShortcutGroup;
  /** For a tool-select shortcut, the tool this key arms. */
  readonly tool?: PlannerTool;
  /** True when the shortcut requires the Cmd/Ctrl modifier. */
  readonly meta?: boolean;
  /** True when the shortcut also requires Shift. */
  readonly shift?: boolean;
  /** True when the chord is desktop (Electron) only (the browser keeps it native). */
  readonly desktopOnly?: boolean;
}

/**
 * Every planner shortcut. Tool letters are unique so no two tools collide; the
 * panel/overlay letters use a disjoint set. Edit/file entries carry their
 * modifiers so a renderer can format the chord.
 */
export const PLANNER_SHORTCUTS: readonly PlannerShortcut[] = [
  // ── Tools ─────────────────────────────────────────────────────────────
  { key: "v", tool: "select", group: "tool", labelKey: "shortcuts.select" },
  { key: "w", tool: "waypoint", group: "tool", labelKey: "shortcuts.waypoint" },
  { key: "k", tool: "takeoff", group: "tool", labelKey: "shortcuts.takeoff" },
  { key: "j", tool: "land", group: "tool", labelKey: "shortcuts.land" },
  { key: "o", tool: "loiter", group: "tool", labelKey: "shortcuts.loiter" },
  { key: "r", tool: "roi", group: "tool", labelKey: "shortcuts.roi" },
  { key: "y", tool: "rally", group: "tool", labelKey: "shortcuts.rally" },
  { key: "b", tool: "poi", group: "tool", labelKey: "shortcuts.poi" },
  { key: "d", tool: "datum", group: "tool", labelKey: "shortcuts.datum" },
  { key: "p", tool: "polygon", group: "tool", labelKey: "shortcuts.polygon" },
  { key: "c", tool: "circle", group: "tool", labelKey: "shortcuts.circle" },
  { key: "m", tool: "measure", group: "tool", labelKey: "shortcuts.measure" },
  // ── Panels ────────────────────────────────────────────────────────────
  { key: "t", group: "panel", labelKey: "shortcuts.terrain" },
  { key: "g", group: "panel", labelKey: "shortcuts.patterns" },
  { key: "i", group: "panel", labelKey: "shortcuts.validation" },
  { key: "/", group: "panel", labelKey: "shortcuts.search" },
  // ── Overlays ──────────────────────────────────────────────────────────
  { key: "l", group: "overlay", labelKey: "shortcuts.overlays" },
  // ── Edit ──────────────────────────────────────────────────────────────
  { key: "z", meta: true, group: "edit", labelKey: "shortcuts.undo" },
  { key: "z", meta: true, shift: true, group: "edit", labelKey: "shortcuts.redo" },
  { key: "C", meta: true, group: "edit", labelKey: "shortcuts.copy" },
  { key: "V", meta: true, group: "edit", labelKey: "shortcuts.paste" },
  { key: "↑↓←→", group: "edit", labelKey: "shortcuts.nudge" },
  { key: "Del", group: "edit", labelKey: "shortcuts.delete" },
  { key: "Esc", group: "edit", labelKey: "shortcuts.cancel" },
  // ── File ──────────────────────────────────────────────────────────────
  { key: "s", meta: true, group: "file", labelKey: "shortcuts.save" },
  { key: "s", meta: true, shift: true, group: "file", labelKey: "shortcuts.saveAs" },
  { key: "n", meta: true, group: "file", labelKey: "shortcuts.newPlan", desktopOnly: true },
];

/** The tool letter for a given tool, or undefined if the tool has no shortcut. */
export function shortcutKeyForTool(tool: PlannerTool): string | undefined {
  return PLANNER_SHORTCUTS.find((s) => s.tool === tool)?.key;
}

/** The plain (no-modifier) tool-select letters, keyed by letter → tool. */
export const TOOL_SHORTCUT_MAP: Readonly<Record<string, PlannerTool>> = Object.fromEntries(
  PLANNER_SHORTCUTS.filter((s) => s.tool && !s.meta).map((s) => [s.key, s.tool!]),
);
