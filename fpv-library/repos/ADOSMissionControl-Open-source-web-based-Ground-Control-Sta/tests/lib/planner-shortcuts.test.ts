import { describe, it, expect } from "vitest";
import {
  PLANNER_SHORTCUTS,
  TOOL_SHORTCUT_MAP,
  shortcutKeyForTool,
} from "@/lib/planner-shortcuts";
import type { PlannerTool } from "@/lib/types";

const ALL_TOOLS: PlannerTool[] = [
  "select", "waypoint", "polygon", "circle", "measure",
  "takeoff", "land", "loiter", "roi", "rally", "datum",
];

describe("PLANNER_SHORTCUTS", () => {
  it("assigns a shortcut to every planner tool", () => {
    for (const tool of ALL_TOOLS) {
      expect(shortcutKeyForTool(tool), `tool ${tool} has a shortcut`).toBeTruthy();
    }
  });

  it("has no duplicate plain-letter keys (a letter arms exactly one thing)", () => {
    const plainKeys = PLANNER_SHORTCUTS.filter((s) => !s.meta).map((s) => s.key.toLowerCase());
    const unique = new Set(plainKeys);
    expect(unique.size).toBe(plainKeys.length);
  });

  it("TOOL_SHORTCUT_MAP maps each plain tool letter back to its tool", () => {
    for (const tool of ALL_TOOLS) {
      const key = shortcutKeyForTool(tool)!;
      expect(TOOL_SHORTCUT_MAP[key]).toBe(tool);
    }
  });

  it("only tool shortcuts carry a tool field", () => {
    for (const s of PLANNER_SHORTCUTS) {
      if (s.group === "tool") expect(s.tool).toBeTruthy();
      else expect(s.tool).toBeUndefined();
    }
  });

  it("every shortcut has a labelKey", () => {
    for (const s of PLANNER_SHORTCUTS) {
      expect(s.labelKey.startsWith("shortcuts.")).toBe(true);
    }
  });
});
