import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  registerCommandProvider,
  getRegisteredCommands,
} from "@/lib/command-palette-registry";
import { buildPlannerCommands, type PlannerCommandHandlers } from "@/app/plan/planner-commands";

function noopHandlers(): PlannerCommandHandlers {
  return {
    setActiveTool: vi.fn(), undo: vi.fn(), redo: vi.fn(),
    handleSave: vi.fn(), handleSaveAs: vi.fn(), handleNewPlan: vi.fn(),
    toggleTerrain: vi.fn(), togglePattern: vi.fn(), toggleValidation: vi.fn(), toggleOverlays: vi.fn(),
  };
}

describe("command-palette-registry", () => {
  it("merges registered providers and unregisters cleanly", () => {
    const unregister = registerCommandProvider(() => [
      { id: "x", label: "Test X", category: "T", action: () => {} },
    ]);
    let cmds = getRegisteredCommands({ query: "", pathname: "/plan" });
    expect(cmds.some((c) => c.id === "x")).toBe(true);
    unregister();
    cmds = getRegisteredCommands({ query: "", pathname: "/plan" });
    expect(cmds.some((c) => c.id === "x")).toBe(false);
  });

  it("passes the context (query + pathname) to providers", () => {
    const provider = vi.fn(() => []);
    const unregister = registerCommandProvider(provider);
    getRegisteredCommands({ query: "abc", pathname: "/sim" });
    expect(provider).toHaveBeenCalledWith({ query: "abc", pathname: "/sim" });
    unregister();
  });
});

describe("buildPlannerCommands", () => {
  const label = (k: string) => k; // identity translator for tests
  beforeEach(() => vi.clearAllMocks());

  it("wires tool + panel + file verbs to their handlers", () => {
    const h = noopHandlers();
    const cmds = buildPlannerCommands(h, label, "Planner", "");
    const byLabel = (k: string) => cmds.find((c) => c.label === k);

    byLabel("shortcuts.select")?.action();
    expect(h.setActiveTool).toHaveBeenCalledWith("select");

    byLabel("shortcuts.overlays")?.action();
    expect(h.toggleOverlays).toHaveBeenCalledTimes(1);

    byLabel("shortcuts.save")?.action();
    expect(h.handleSave).toHaveBeenCalledTimes(1);

    byLabel("shortcuts.undo")?.action();
    expect(h.undo).toHaveBeenCalledTimes(1);
  });

  it("omits context-scoped shortcuts (delete / cancel) that have no standalone verb", () => {
    const cmds = buildPlannerCommands(noopHandlers(), label, "Planner", "");
    expect(cmds.some((c) => c.label === "shortcuts.delete")).toBe(false);
    expect(cmds.some((c) => c.label === "shortcuts.cancel")).toBe(false);
  });

  it("filters by the query (case-insensitive label match)", () => {
    const cmds = buildPlannerCommands(noopHandlers(), label, "Planner", "waypoint");
    expect(cmds.length).toBe(1);
    expect(cmds[0].label).toBe("shortcuts.waypoint");
  });

  it("tags every command with the given category", () => {
    const cmds = buildPlannerCommands(noopHandlers(), label, "Planner", "");
    expect(cmds.every((c) => c.category === "Planner")).toBe(true);
    expect(cmds.length).toBeGreaterThan(0);
  });
});
