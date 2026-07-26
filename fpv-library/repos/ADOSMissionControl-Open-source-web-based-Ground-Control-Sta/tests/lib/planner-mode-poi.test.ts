/**
 * Unit tests for the POI additions to the planner interaction-mode machine.
 * The "poi" tool must mirror the "rally" placement tool exactly: it maps to a
 * dedicated placement mode, round-trips through tool<->mode, is treated as a
 * placement mode, and carries no drawing/datum sub-state.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  modeForTool,
  toolForMode,
  transition,
  isPlacementMode,
  isDrawMode,
  drawingModeFor,
  datumPatternFor,
  type PlannerMode,
} from "@/lib/planner-mode";

describe("planner-mode poi tool", () => {
  it("poi -> poi mode", () => {
    expect(modeForTool("poi")).toEqual({ kind: "poi" });
  });

  it("modeForTool then toolForMode round-trips poi", () => {
    expect(toolForMode(modeForTool("poi"))).toBe("poi");
  });

  it("selecting the poi tool from any dirty mode yields a clean poi mode", () => {
    const dirty: PlannerMode[] = [
      { kind: "draw", shape: "polygon", drawingFor: "pattern" },
      { kind: "datum", pattern: "expandingSquare" },
      { kind: "rally" },
      { kind: "waypoint", tool: "takeoff" },
    ];
    for (const start of dirty) {
      expect(transition(start, { type: "selectTool", tool: "poi" })).toEqual({ kind: "poi" });
    }
  });

  it("reset from poi returns to select", () => {
    expect(transition({ kind: "poi" }, { type: "reset" })).toEqual({ kind: "select" });
  });

  it("poi is a placement mode, not a draw mode", () => {
    expect(isPlacementMode({ kind: "poi" })).toBe(true);
    expect(isDrawMode({ kind: "poi" })).toBe(false);
  });

  it("poi carries no drawing or datum sub-state", () => {
    expect(drawingModeFor({ kind: "poi" })).toBeNull();
    expect(datumPatternFor({ kind: "poi" })).toBeNull();
  });
});
