/**
 * @module planner-mode
 * @description Single source of truth for the mission planner's interaction mode.
 *
 * The planner's "what is the map doing right now" state used to live in four
 * separate places (the active toolbar tool, the active flight-pattern type, the
 * drawing-tool mode, and an in-progress datum-placement arm) that were kept in
 * sync by hand. Switching the toolbar tool did not clear the sibling sub-modes,
 * so a stale pattern type or drawing mode could leak across a tool switch.
 *
 * This module models the interaction as ONE discriminated union and provides a
 * pure reducer that, on any tool switch, returns a fresh mode with no residue of
 * the previous sub-mode. The legacy fields are derived from this single value.
 *
 * Pure module: no Zustand, no React, no side effects. Mirrors the purity of the
 * pattern generators so the whole transition table is unit-testable.
 *
 * @license GPL-3.0-only
 */

import type { DrawingMode } from "@/lib/drawing/types";
import type { PlannerTool } from "@/lib/types/mission";

/**
 * The flight-pattern types whose origin point is set by clicking the map.
 * A datum-placement mode arms exactly one of these (or null when no SAR
 * pattern is currently selected — the datum tool can still be armed for the
 * generic "set the pattern origin" gesture).
 */
export type DatumPattern =
  | "survey"
  | "orbit"
  | "corridor"
  | "expandingSquare"
  | "sectorSearch"
  | "parallelTrack"
  | "structureScan"
  | null;

/** The map-drawing shape a `draw` mode produces. */
export type DrawShape = "polygon" | "circle" | "measure";

/**
 * What a drawn shape is for. This tags the eventual destination of a completed
 * shape so a later refactor can route it deterministically (a geofence editor, a
 * flight-pattern boundary, or a free-standing annotation) instead of relying on
 * hidden precedence. The field is REQUIRED on every `draw` mode now so the shape
 * of the union is frozen, even though the toolbar today only ever produces
 * `"free"` draws.
 */
export type DrawingFor = "geofence" | "pattern" | "free";

/** Idle: clicking the map selects / inspects existing features. */
export interface SelectMode {
  readonly kind: "select";
}

/**
 * Placement: each map click drops a feature of the given `tool` kind. Covers
 * the plain waypoint tool and the typed command-placement tools (takeoff, land,
 * loiter, roi). The specific `tool` is carried so the legacy `activeTool` field
 * round-trips losslessly.
 */
export interface WaypointMode {
  readonly kind: "waypoint";
  /** The placement tool that is armed. */
  readonly tool: "waypoint" | "takeoff" | "land" | "loiter" | "roi";
}

/** Drawing a shape on the map. */
export interface DrawMode {
  readonly kind: "draw";
  /** The shape being drawn. */
  readonly shape: DrawShape;
  /** Where the completed shape is destined. */
  readonly drawingFor: DrawingFor;
}

/**
 * Placing a flight-pattern origin (datum) by clicking the map. Carries the SAR
 * pattern the datum arms so the placement knows which config to write the point
 * into; `null` when no pattern is selected.
 */
export interface DatumMode {
  readonly kind: "datum";
  /** The pattern whose origin this placement sets. */
  readonly pattern: DatumPattern;
}

/** Placing a rally point by clicking the map. */
export interface RallyMode {
  readonly kind: "rally";
}

/** Placing a plan-attached point of interest by clicking the map. */
export interface PoiMode {
  readonly kind: "poi";
}

/** The complete interaction-mode union. */
export type PlannerMode =
  | SelectMode
  | WaypointMode
  | DrawMode
  | DatumMode
  | RallyMode
  | PoiMode;

/** The idle default the planner boots into. */
export const DEFAULT_PLANNER_MODE: PlannerMode = { kind: "select" };

/**
 * Events the reducer accepts. Each event yields a fresh mode with no residue of
 * the previous sub-mode (the cross-clear that prevents a stale sibling leaking).
 */
export type PlannerModeEvent =
  /** The operator picked a toolbar tool. */
  | { type: "selectTool"; tool: PlannerTool }
  /** Arm a draw with an explicit destination (e.g. a geofence or pattern boundary). */
  | { type: "startDraw"; shape: DrawShape; drawingFor: DrawingFor }
  /** Arm datum placement for a specific SAR pattern. */
  | { type: "armDatum"; pattern: DatumPattern }
  /** Return to the idle select mode. */
  | { type: "reset" };

/**
 * Map a toolbar tool to the corresponding interaction mode. Every transition
 * starts from scratch, so picking any tool drops whatever sub-mode was active.
 * Drawing tools default `drawingFor` to `"free"` (the toolbar's plain
 * polygon/circle/measure gesture); the datum tool arms with no pattern until a
 * caller specifies one via `armDatum`.
 */
export function modeForTool(tool: PlannerTool): PlannerMode {
  switch (tool) {
    case "select":
      return { kind: "select" };
    case "waypoint":
    case "takeoff":
    case "land":
    case "loiter":
    case "roi":
      return { kind: "waypoint", tool };
    case "polygon":
    case "circle":
    case "measure":
      return { kind: "draw", shape: tool, drawingFor: "free" };
    case "datum":
      return { kind: "datum", pattern: null };
    case "rally":
      return { kind: "rally" };
    case "poi":
      return { kind: "poi" };
  }
}

/**
 * Pure reducer. Given the current mode and an event, returns the next mode.
 * Crucially, the result never carries residue from the previous mode: a
 * `selectTool` rebuilds the mode wholesale from the tool, `startDraw` /
 * `armDatum` build a single fresh sub-mode, and `reset` returns to select.
 */
export function transition(_mode: PlannerMode, event: PlannerModeEvent): PlannerMode {
  switch (event.type) {
    case "selectTool":
      return modeForTool(event.tool);
    case "startDraw":
      return { kind: "draw", shape: event.shape, drawingFor: event.drawingFor };
    case "armDatum":
      return { kind: "datum", pattern: event.pattern };
    case "reset":
      return { kind: "select" };
  }
}

/**
 * Derive the legacy `activeTool` value from a mode, so existing consumers that
 * read `activeTool` keep working while `mode` is the authoritative state.
 */
export function toolForMode(mode: PlannerMode): PlannerTool {
  switch (mode.kind) {
    case "select":
      return "select";
    case "waypoint":
      return mode.tool;
    case "draw":
      return mode.shape;
    case "datum":
      return "datum";
    case "rally":
      return "rally";
    case "poi":
      return "poi";
  }
}

/** True when clicking the map drops a feature (placement / datum / rally / poi). */
export function isPlacementMode(mode: PlannerMode): boolean {
  return (
    mode.kind === "waypoint" ||
    mode.kind === "datum" ||
    mode.kind === "rally" ||
    mode.kind === "poi"
  );
}

/** True when the planner is actively drawing a shape. */
export function isDrawMode(mode: PlannerMode): boolean {
  return mode.kind === "draw";
}

/**
 * Map a mode to the existing `DrawingMode` value the drawing store / manager
 * understand. A `draw` mode yields its shape; everything else yields `null`
 * (idle), which is exactly what the drawing store should hold while a non-draw
 * tool is active. This is the derivation that replaces the manual drawing-mode
 * sync.
 */
export function drawingModeFor(mode: PlannerMode): DrawingMode {
  return mode.kind === "draw" ? mode.shape : null;
}

/**
 * The SAR pattern a datum mode arms, or `null` when the mode is not a datum
 * placement (or no pattern is selected). Lets the placement path read the armed
 * pattern off the single mode value.
 */
export function datumPatternFor(mode: PlannerMode): DatumPattern {
  return mode.kind === "datum" ? mode.pattern : null;
}
