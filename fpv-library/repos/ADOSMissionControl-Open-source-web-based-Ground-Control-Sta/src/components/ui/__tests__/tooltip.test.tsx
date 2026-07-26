/**
 * @module TooltipTest
 * @description Component tests for the portaled tooltip primitive.
 * Pins the viewport-aware clamp, the cursor-into-overlay stay-open
 * behaviour, and the Esc-closes-overlay path.
 *
 * @license GPL-3.0-only
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { Tooltip } from "../tooltip";

// Stub a small viewport so the clamp logic has well-defined edges.
const VIEWPORT_WIDTH = 1024;
const VIEWPORT_HEIGHT = 768;

beforeEach(() => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: VIEWPORT_WIDTH,
  });
  Object.defineProperty(window, "innerHeight", {
    configurable: true,
    value: VIEWPORT_HEIGHT,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function stubRect(rect: Partial<DOMRect>): DOMRect {
  const base: DOMRect = {
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: 0,
    height: 0,
    toJSON: () => ({}),
  };
  return { ...base, ...rect } as DOMRect;
}

describe("Tooltip — viewport clamp", () => {
  it("clamps the overlay inside the right edge when the trigger sits near the edge", () => {
    // Trigger sits 10px from the right edge of a 1024px viewport.
    const triggerRect = stubRect({
      top: 200,
      left: VIEWPORT_WIDTH - 30,
      right: VIEWPORT_WIDTH - 10,
      bottom: 220,
      width: 20,
      height: 20,
    });
    // Overlay is 384px wide (24rem at 16px root) — wider than the
    // 20px headroom remaining on the right.
    const overlayRect = stubRect({
      width: 384,
      height: 80,
    });

    const originalProto = HTMLElement.prototype.getBoundingClientRect;
    HTMLElement.prototype.getBoundingClientRect = function () {
      if (this.getAttribute("role") === "tooltip") return overlayRect;
      return triggerRect;
    };
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
      configurable: true,
      get() {
        if (this.getAttribute("role") === "tooltip") return 384;
        return 20;
      },
    });
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
      configurable: true,
      get() {
        if (this.getAttribute("role") === "tooltip") return 80;
        return 20;
      },
    });

    try {
      render(
        <Tooltip content="A long sentence that should never get clipped" multiline>
          <button type="button">help</button>
        </Tooltip>,
      );

      act(() => {
        fireEvent.mouseEnter(screen.getByRole("button").parentElement!);
      });

      const overlay = screen.getByRole("tooltip");
      const left = parseFloat(overlay.style.left);
      // The overlay must sit inside an 8px right margin.
      expect(left + 384).toBeLessThanOrEqual(VIEWPORT_WIDTH - 8);
      expect(left).toBeGreaterThanOrEqual(8);
    } finally {
      HTMLElement.prototype.getBoundingClientRect = originalProto;
    }
  });
});

describe("Tooltip — stay-open over the cursor", () => {
  it("cancels the close timer when the cursor enters the overlay", () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="hello world">
        <button type="button">help</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole("button").parentElement!;
    act(() => {
      fireEvent.mouseEnter(trigger);
    });
    expect(screen.queryByRole("tooltip")).toBeInTheDocument();

    // Schedule close, then move into the overlay before the 150ms
    // timer fires. The overlay must stay mounted.
    act(() => {
      fireEvent.mouseLeave(trigger);
    });
    const overlay = screen.getByRole("tooltip");
    act(() => {
      fireEvent.mouseEnter(overlay);
      vi.advanceTimersByTime(300);
    });
    expect(screen.queryByRole("tooltip")).toBeInTheDocument();
  });
});

describe("Tooltip — Esc closes", () => {
  it("closes on Escape key after open", () => {
    render(
      <Tooltip content="hello world">
        <button type="button">help</button>
      </Tooltip>,
    );
    act(() => {
      fireEvent.mouseEnter(screen.getByRole("button").parentElement!);
    });
    expect(screen.queryByRole("tooltip")).toBeInTheDocument();
    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

describe("Tooltip — empty content renders nothing", () => {
  it("does not portal when content is an empty string", () => {
    render(
      <Tooltip content="">
        <button type="button">help</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole("button").parentElement!;
    act(() => {
      fireEvent.mouseEnter(trigger);
    });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
