/**
 * Unit tests for the single planner keyboard dispatcher: typing-target guard,
 * the Escape / Backspace precedence ordering against an active draw, and the
 * Electron-only gating of the New / Open accelerator chords.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

// Control the active-draw surface the dispatcher reads.
const getActiveDrawApi = vi.fn();
vi.mock("@/lib/drawing/drawing-manager", () => ({
  getActiveDrawApi: () => getActiveDrawApi(),
}));

// Keep the real isTypingTarget, but make isElectron controllable per test.
const isElectron = vi.fn(() => false);
vi.mock("@/lib/utils", async () => {
  const actual = await vi.importActual<typeof import("@/lib/utils")>("@/lib/utils");
  return { ...actual, isElectron: () => isElectron() };
});

import { useKeyboardShortcuts } from "@/app/plan/use-keyboard-shortcuts";
import type { PlannerTool } from "@/lib/types";

type Params = Parameters<typeof useKeyboardShortcuts>[0];

/** Build a params object with vi.fn() spies and sensible defaults, overridable. */
function makeParams(overrides: Partial<Params> = {}): Params {
  return {
    activeTool: "select" as PlannerTool,
    setActiveTool: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    selectedWaypointId: null,
    removeWaypoint: vi.fn(),
    setSelectedWaypoint: vi.fn(),
    expandedWaypointId: null,
    setExpandedWaypoint: vi.fn(),
    handleSave: vi.fn(),
    handleSaveAs: vi.fn(),
    handleNewPlan: vi.fn(),
    handleFocusSearch: vi.fn(),
    onTogglePatternEditor: vi.fn(),
    onToggleValidation: vi.fn(),
    onToggleTerrain: vi.fn(),
    ...overrides,
  };
}

/** Make a fake ActiveDrawApi whose isDrawing() returns the given flag. */
function drawApi(isDrawing: boolean) {
  return {
    isDrawing: () => isDrawing,
    cancel: vi.fn(),
    popVertex: vi.fn(),
    complete: vi.fn(),
  };
}

/** Dispatch a keydown on document, optionally from a typing target. */
function press(key: string, opts: KeyboardEventInit & { typing?: boolean } = {}) {
  const { typing, ...init } = opts;
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init });
  if (typing) {
    const input = document.createElement("input");
    document.body.appendChild(input);
    Object.defineProperty(event, "target", { value: input, configurable: true });
  }
  document.dispatchEvent(event);
  return event;
}

beforeEach(() => {
  getActiveDrawApi.mockReturnValue(null);
  isElectron.mockReturnValue(false);
  document.body.innerHTML = "";
});

describe("planner keyboard dispatcher", () => {
  it("ignores shortcuts fired from a typing target", () => {
    const params = makeParams();
    renderHook(() => useKeyboardShortcuts(params));

    press("w", { typing: true });
    press("Escape", { typing: true });
    press("Backspace", { typing: true, key: "Backspace" });

    expect(params.setActiveTool).not.toHaveBeenCalled();
  });

  it("selects a tool on its letter shortcut", () => {
    const params = makeParams();
    renderHook(() => useKeyboardShortcuts(params));
    press("w");
    expect(params.setActiveTool).toHaveBeenCalledWith("waypoint");
    press("p");
    expect(params.setActiveTool).toHaveBeenCalledWith("polygon");
  });

  it("Escape cancels an active draw before any generic clear", () => {
    const api = drawApi(true);
    getActiveDrawApi.mockReturnValue(api);
    const params = makeParams({ activeTool: "polygon", expandedWaypointId: "wp-1" });
    renderHook(() => useKeyboardShortcuts(params));

    press("Escape");

    expect(api.cancel).toHaveBeenCalledTimes(1);
    expect(params.setActiveTool).toHaveBeenCalledWith("select");
    // The expanded-waypoint collapse must NOT run while a draw was cancelled.
    expect(params.setExpandedWaypoint).not.toHaveBeenCalled();
  });

  it("Escape collapses an expanded waypoint when not drawing", () => {
    const params = makeParams({ activeTool: "select", expandedWaypointId: "wp-1" });
    renderHook(() => useKeyboardShortcuts(params));
    press("Escape");
    expect(params.setExpandedWaypoint).toHaveBeenCalledWith(null);
    expect(params.setActiveTool).not.toHaveBeenCalled();
  });

  it("Escape clears a non-select tool to select when not drawing", () => {
    const params = makeParams({ activeTool: "waypoint", expandedWaypointId: null });
    renderHook(() => useKeyboardShortcuts(params));
    press("Escape");
    expect(params.setActiveTool).toHaveBeenCalledWith("select");
  });

  it("Backspace pops a draw vertex while drawing and never deletes a waypoint", () => {
    const api = drawApi(true);
    getActiveDrawApi.mockReturnValue(api);
    const params = makeParams({ activeTool: "polygon", selectedWaypointId: "wp-9" });
    renderHook(() => useKeyboardShortcuts(params));

    press("Backspace");

    expect(api.popVertex).toHaveBeenCalledTimes(1);
    expect(params.removeWaypoint).not.toHaveBeenCalled();
  });

  it("Backspace deletes the selected waypoint when not drawing", () => {
    const params = makeParams({ activeTool: "select", selectedWaypointId: "wp-9" });
    renderHook(() => useKeyboardShortcuts(params));

    press("Backspace");

    expect(params.removeWaypoint).toHaveBeenCalledWith("wp-9");
    expect(params.setSelectedWaypoint).toHaveBeenCalledWith(null);
  });

  it("Delete is ignored while drawing (only Backspace pops a vertex)", () => {
    const api = drawApi(true);
    getActiveDrawApi.mockReturnValue(api);
    const params = makeParams({ activeTool: "polygon", selectedWaypointId: "wp-9" });
    renderHook(() => useKeyboardShortcuts(params));

    press("Delete");

    expect(api.popVertex).not.toHaveBeenCalled();
    expect(params.removeWaypoint).not.toHaveBeenCalled();
  });

  it("falls back to the active tool when no draw manager is registered", () => {
    getActiveDrawApi.mockReturnValue(null);
    const params = makeParams({ activeTool: "polygon", selectedWaypointId: "wp-9" });
    renderHook(() => useKeyboardShortcuts(params));

    // No manager, but the tool is a drawing tool, so Backspace must not delete.
    press("Backspace");
    expect(params.removeWaypoint).not.toHaveBeenCalled();
  });

  describe("Electron-only accelerator chords", () => {
    it("does NOT hijack Cmd/Ctrl+N or Cmd/Ctrl+O in the browser", () => {
      isElectron.mockReturnValue(false);
      const params = makeParams();
      renderHook(() => useKeyboardShortcuts(params));

      const newEvent = press("n", { metaKey: true });
      const openEvent = press("o", { metaKey: true });

      expect(params.handleNewPlan).not.toHaveBeenCalled();
      expect(params.handleFocusSearch).not.toHaveBeenCalled();
      // The native chord is left intact (not prevented).
      expect(newEvent.defaultPrevented).toBe(false);
      expect(openEvent.defaultPrevented).toBe(false);
    });

    it("fires New / Open in the desktop build", () => {
      isElectron.mockReturnValue(true);
      const params = makeParams();
      renderHook(() => useKeyboardShortcuts(params));

      const newEvent = press("n", { metaKey: true });
      press("o", { metaKey: true });

      expect(params.handleNewPlan).toHaveBeenCalledTimes(1);
      expect(params.handleFocusSearch).toHaveBeenCalledTimes(1);
      expect(newEvent.defaultPrevented).toBe(true);
    });
  });

  it("Save and Save-As fire on Cmd/Ctrl+S regardless of platform", () => {
    const params = makeParams();
    renderHook(() => useKeyboardShortcuts(params));

    press("s", { metaKey: true });
    expect(params.handleSave).toHaveBeenCalledTimes(1);

    press("s", { metaKey: true, shiftKey: true });
    expect(params.handleSaveAs).toHaveBeenCalledTimes(1);
  });

  describe("arrow-key nudge of the selected waypoint", () => {
    it("nudges the selected waypoint a fine step per direction", () => {
      const onNudgeSelected = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onNudgeSelected });
      renderHook(() => useKeyboardShortcuts(params));

      const up = press("ArrowUp");
      expect(onNudgeSelected).toHaveBeenLastCalledWith(1e-5, 0);
      expect(up.defaultPrevented).toBe(true);

      press("ArrowDown");
      expect(onNudgeSelected).toHaveBeenLastCalledWith(-1e-5, 0);

      press("ArrowLeft");
      expect(onNudgeSelected).toHaveBeenLastCalledWith(0, -1e-5);

      press("ArrowRight");
      expect(onNudgeSelected).toHaveBeenLastCalledWith(0, 1e-5);
    });

    it("uses a coarser step when Shift is held", () => {
      const onNudgeSelected = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onNudgeSelected });
      renderHook(() => useKeyboardShortcuts(params));

      press("ArrowUp", { shiftKey: true });
      expect(onNudgeSelected).toHaveBeenLastCalledWith(1e-4, 0);
    });

    it("does not nudge (or preventDefault) with no selected waypoint", () => {
      const onNudgeSelected = vi.fn();
      const params = makeParams({ selectedWaypointId: null, onNudgeSelected });
      renderHook(() => useKeyboardShortcuts(params));

      const up = press("ArrowUp");
      expect(onNudgeSelected).not.toHaveBeenCalled();
      expect(up.defaultPrevented).toBe(false);
    });

    it("ignores arrows while typing in a field", () => {
      const onNudgeSelected = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onNudgeSelected });
      renderHook(() => useKeyboardShortcuts(params));

      press("ArrowUp", { typing: true });
      expect(onNudgeSelected).not.toHaveBeenCalled();
    });
  });

  describe("copy / paste of the selected waypoint(s)", () => {
    it("Cmd/Ctrl+C fires onCopy when no text is selected", () => {
      const onCopy = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onCopy });
      renderHook(() => useKeyboardShortcuts(params));

      const e = press("c", { metaKey: true });
      expect(onCopy).toHaveBeenCalledTimes(1);
      expect(e.defaultPrevented).toBe(true);
    });

    it("Cmd/Ctrl+V fires onPaste", () => {
      const onPaste = vi.fn();
      const params = makeParams({ onPaste });
      renderHook(() => useKeyboardShortcuts(params));

      const e = press("v", { metaKey: true });
      expect(onPaste).toHaveBeenCalledTimes(1);
      expect(e.defaultPrevented).toBe(true);
    });

    it("does not fire copy/paste while typing in a field", () => {
      const onCopy = vi.fn();
      const onPaste = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onCopy, onPaste });
      renderHook(() => useKeyboardShortcuts(params));

      press("c", { metaKey: true, typing: true });
      press("v", { metaKey: true, typing: true });
      expect(onCopy).not.toHaveBeenCalled();
      expect(onPaste).not.toHaveBeenCalled();
    });

    it("plain 'c' still selects the circle tool (copy needs the modifier)", () => {
      const onCopy = vi.fn();
      const params = makeParams({ onCopy });
      renderHook(() => useKeyboardShortcuts(params));

      press("c");
      expect(params.setActiveTool).toHaveBeenCalledWith("circle");
      expect(onCopy).not.toHaveBeenCalled();
    });

    it("does not hijack Cmd/Ctrl+C while text is selected on the page", () => {
      const onCopy = vi.fn();
      const params = makeParams({ selectedWaypointId: "wp-1", onCopy });
      renderHook(() => useKeyboardShortcuts(params));

      const original = window.getSelection;
      window.getSelection = () =>
        ({ toString: () => "highlighted text" }) as unknown as Selection;
      try {
        const e = press("c", { metaKey: true });
        expect(onCopy).not.toHaveBeenCalled();
        expect(e.defaultPrevented).toBe(false);
      } finally {
        window.getSelection = original;
      }
    });
  });
});
