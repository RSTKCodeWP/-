import { describe, it, expect } from "vitest";
import {
  DEFAULT_PLANNER_MODE,
  modeForTool,
  transition,
  toolForMode,
  isPlacementMode,
  isDrawMode,
  drawingModeFor,
  datumPatternFor,
  type PlannerMode,
  type DatumPattern,
} from "@/lib/planner-mode";
import type { PlannerTool } from "@/lib/types/mission";

const ALL_TOOLS: PlannerTool[] = [
  "select",
  "waypoint",
  "takeoff",
  "land",
  "loiter",
  "roi",
  "rally",
  "polygon",
  "circle",
  "measure",
  "datum",
];

const PLACEMENT_TOOLS: PlannerTool[] = ["waypoint", "takeoff", "land", "loiter", "roi"];
const DRAW_TOOLS: PlannerTool[] = ["polygon", "circle", "measure"];

describe("planner-mode", () => {
  it("default mode is select", () => {
    expect(DEFAULT_PLANNER_MODE).toEqual({ kind: "select" });
  });

  // ------- modeForTool: every tool maps to the right mode kind -------
  describe("modeForTool", () => {
    it("select -> select", () => {
      expect(modeForTool("select")).toEqual({ kind: "select" });
    });

    it.each(PLACEMENT_TOOLS)("placement tool %s -> waypoint mode carrying the tool", (tool) => {
      expect(modeForTool(tool)).toEqual({ kind: "waypoint", tool });
    });

    it.each(DRAW_TOOLS)("draw tool %s -> draw mode with shape and drawingFor=free", (tool) => {
      expect(modeForTool(tool)).toEqual({ kind: "draw", shape: tool, drawingFor: "free" });
    });

    it("datum -> datum mode with no armed pattern", () => {
      expect(modeForTool("datum")).toEqual({ kind: "datum", pattern: null });
    });

    it("rally -> rally mode", () => {
      expect(modeForTool("rally")).toEqual({ kind: "rally" });
    });
  });

  // ------- toolForMode round-trips every tool -------
  describe("toolForMode round-trip", () => {
    it.each(ALL_TOOLS)("modeForTool then toolForMode returns the original tool: %s", (tool) => {
      expect(toolForMode(modeForTool(tool))).toBe(tool);
    });
  });

  // ------- transition: selecting any tool clears all sibling sub-modes -------
  describe("transition selectTool clears residue", () => {
    // Build a set of "dirty" starting modes carrying sub-mode state.
    const dirtyModes: PlannerMode[] = [
      { kind: "draw", shape: "polygon", drawingFor: "pattern" },
      { kind: "draw", shape: "circle", drawingFor: "geofence" },
      { kind: "datum", pattern: "expandingSquare" },
      { kind: "rally" },
      { kind: "waypoint", tool: "takeoff" },
    ];

    for (const start of dirtyModes) {
      for (const tool of ALL_TOOLS) {
        it(`from ${start.kind} -> selectTool ${tool} yields the fresh tool mode`, () => {
          const next = transition(start, { type: "selectTool", tool });
          // The next mode is exactly what the tool maps to, with zero residue.
          expect(next).toEqual(modeForTool(tool));
        });
      }
    }

    it("switching from a pattern-armed draw to select carries no shape/drawingFor", () => {
      const start: PlannerMode = { kind: "draw", shape: "polygon", drawingFor: "pattern" };
      const next = transition(start, { type: "selectTool", tool: "select" });
      expect(next).toEqual({ kind: "select" });
      expect("shape" in next).toBe(false);
      expect("drawingFor" in next).toBe(false);
    });

    it("switching from an armed datum to a draw tool drops the armed pattern", () => {
      const start: PlannerMode = { kind: "datum", pattern: "sectorSearch" };
      const next = transition(start, { type: "selectTool", tool: "circle" });
      expect(next).toEqual({ kind: "draw", shape: "circle", drawingFor: "free" });
      expect("pattern" in next).toBe(false);
    });

    it("switching between two placement tools replaces the carried tool", () => {
      const start: PlannerMode = { kind: "waypoint", tool: "waypoint" };
      const next = transition(start, { type: "selectTool", tool: "roi" });
      expect(next).toEqual({ kind: "waypoint", tool: "roi" });
    });
  });

  // ------- transition: startDraw / armDatum / reset build fresh sub-modes -------
  describe("transition explicit sub-mode events", () => {
    it("startDraw builds a draw mode carrying shape and drawingFor", () => {
      const next = transition({ kind: "select" }, { type: "startDraw", shape: "polygon", drawingFor: "geofence" });
      expect(next).toEqual({ kind: "draw", shape: "polygon", drawingFor: "geofence" });
    });

    it("startDraw from a datum mode drops the armed pattern", () => {
      const start: PlannerMode = { kind: "datum", pattern: "survey" };
      const next = transition(start, { type: "startDraw", shape: "circle", drawingFor: "pattern" });
      expect(next).toEqual({ kind: "draw", shape: "circle", drawingFor: "pattern" });
    });

    it("armDatum builds a datum mode carrying the pattern", () => {
      const next = transition({ kind: "select" }, { type: "armDatum", pattern: "parallelTrack" });
      expect(next).toEqual({ kind: "datum", pattern: "parallelTrack" });
    });

    it("armDatum with null pattern is allowed (generic datum arm)", () => {
      const next = transition({ kind: "select" }, { type: "armDatum", pattern: null });
      expect(next).toEqual({ kind: "datum", pattern: null });
    });

    it("armDatum from a draw mode drops shape and drawingFor", () => {
      const start: PlannerMode = { kind: "draw", shape: "measure", drawingFor: "free" };
      const next = transition(start, { type: "armDatum", pattern: "orbit" });
      expect(next).toEqual({ kind: "datum", pattern: "orbit" });
      expect("shape" in next).toBe(false);
    });

    it("reset returns to select from any mode", () => {
      const starts: PlannerMode[] = [
        { kind: "draw", shape: "polygon", drawingFor: "pattern" },
        { kind: "datum", pattern: "expandingSquare" },
        { kind: "rally" },
        { kind: "waypoint", tool: "loiter" },
      ];
      for (const start of starts) {
        expect(transition(start, { type: "reset" })).toEqual({ kind: "select" });
      }
    });
  });

  // ------- isPlacementMode -------
  describe("isPlacementMode", () => {
    it("waypoint, datum, rally are placement modes", () => {
      expect(isPlacementMode({ kind: "waypoint", tool: "waypoint" })).toBe(true);
      expect(isPlacementMode({ kind: "datum", pattern: null })).toBe(true);
      expect(isPlacementMode({ kind: "rally" })).toBe(true);
    });

    it("select and draw are not placement modes", () => {
      expect(isPlacementMode({ kind: "select" })).toBe(false);
      expect(isPlacementMode({ kind: "draw", shape: "polygon", drawingFor: "free" })).toBe(false);
    });
  });

  // ------- isDrawMode -------
  describe("isDrawMode", () => {
    it("draw is a draw mode", () => {
      expect(isDrawMode({ kind: "draw", shape: "circle", drawingFor: "free" })).toBe(true);
    });

    it("non-draw modes are not draw modes", () => {
      expect(isDrawMode({ kind: "select" })).toBe(false);
      expect(isDrawMode({ kind: "waypoint", tool: "waypoint" })).toBe(false);
      expect(isDrawMode({ kind: "datum", pattern: null })).toBe(false);
      expect(isDrawMode({ kind: "rally" })).toBe(false);
    });
  });

  // ------- drawingModeFor -------
  describe("drawingModeFor", () => {
    it.each(["polygon", "circle", "measure"] as const)("draw %s -> %s drawing mode", (shape) => {
      expect(drawingModeFor({ kind: "draw", shape, drawingFor: "free" })).toBe(shape);
    });

    it("non-draw modes -> null drawing mode", () => {
      expect(drawingModeFor({ kind: "select" })).toBeNull();
      expect(drawingModeFor({ kind: "waypoint", tool: "land" })).toBeNull();
      expect(drawingModeFor({ kind: "datum", pattern: "survey" })).toBeNull();
      expect(drawingModeFor({ kind: "rally" })).toBeNull();
    });
  });

  // ------- datumPatternFor -------
  describe("datumPatternFor", () => {
    it.each<DatumPattern>([
      "survey",
      "orbit",
      "corridor",
      "expandingSquare",
      "sectorSearch",
      "parallelTrack",
      "structureScan",
      null,
    ])("datum mode armed with %s reports that pattern", (pattern) => {
      expect(datumPatternFor({ kind: "datum", pattern })).toBe(pattern);
    });

    it("non-datum modes report null", () => {
      expect(datumPatternFor({ kind: "select" })).toBeNull();
      expect(datumPatternFor({ kind: "draw", shape: "polygon", drawingFor: "free" })).toBeNull();
      expect(datumPatternFor({ kind: "waypoint", tool: "waypoint" })).toBeNull();
      expect(datumPatternFor({ kind: "rally" })).toBeNull();
    });
  });
});
