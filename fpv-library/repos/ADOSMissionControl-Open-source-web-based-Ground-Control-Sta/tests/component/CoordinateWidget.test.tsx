import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));

let demo = false;
vi.mock("@/lib/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/utils")>()),
  isDemoMode: () => demo,
}));

const getElevationSpy = vi.fn();
vi.mock("@/lib/terrain/terrain-provider", () => ({
  getElevation: (...a: unknown[]) => getElevationSpy(...a),
}));

// Keep the test focused on the cursor readout — the format Select has its own
// portal/DOM behavior and is not what these assertions exercise.
vi.mock("@/components/ui/select", () => ({ Select: () => null }));

// The settings store is persisted via indexedDBStorage; stub the backing store.
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn().mockResolvedValue(null),
      setItem: vi.fn().mockResolvedValue(undefined),
      removeItem: vi.fn().mockResolvedValue(undefined),
    }),
  },
}));

import { CoordinateWidget } from "@/components/planner/CoordinateWidget";
import { CURSOR_MOVE_EVENT } from "@/lib/planner/cursor-coord";

function moveTo(lat: number, lon: number) {
  act(() => {
    window.dispatchEvent(new CustomEvent(CURSOR_MOVE_EVENT, { detail: { lat, lon } }));
  });
}

function mouseOut() {
  act(() => {
    window.dispatchEvent(new CustomEvent(CURSOR_MOVE_EVENT, { detail: null }));
  });
}

describe("CoordinateWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    demo = false;
    getElevationSpy.mockResolvedValue(123);
    cleanup();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows no coordinate until a cursor move arrives", () => {
    render(<CoordinateWidget />);
    expect(screen.queryByText(/cursorElevation/)).toBeNull();
  });

  it("shows the cursor coordinate to 6 decimals and a pending elevation", () => {
    render(<CoordinateWidget />);
    moveTo(12.345678, 77.5946);
    expect(screen.getByText("12.345678, 77.594600")).toBeInTheDocument();
    // Elevation lookup is debounced, so it reads as pending until the timer fires.
    expect(screen.getByText("cursorElevation: …")).toBeInTheDocument();
    expect(getElevationSpy).not.toHaveBeenCalled();
  });

  it("fetches the elevation after the debounce and renders it", async () => {
    render(<CoordinateWidget />);
    moveTo(12.345678, 77.5946);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(getElevationSpy).toHaveBeenCalledTimes(1);
    expect(getElevationSpy.mock.calls[0][0]).toBeCloseTo(12.345678);
    expect(getElevationSpy.mock.calls[0][1]).toBeCloseTo(77.5946);
    expect(screen.getByText("cursorElevation: 123 m")).toBeInTheDocument();
  });

  it("debounces a rapid burst of moves into a single lookup at the last point", async () => {
    render(<CoordinateWidget />);
    moveTo(1, 1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    moveTo(2, 2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(getElevationSpy).toHaveBeenCalledTimes(1);
    expect(getElevationSpy.mock.calls[0][0]).toBeCloseTo(2);
  });

  it("skips the network in demo mode and shows a dash for elevation", async () => {
    demo = true;
    render(<CoordinateWidget />);
    moveTo(12.345678, 77.5946);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(getElevationSpy).not.toHaveBeenCalled();
    expect(screen.getByText("cursorElevation: —")).toBeInTheDocument();
  });

  it("hides the readout when the cursor leaves the map", () => {
    render(<CoordinateWidget />);
    moveTo(12.345678, 77.5946);
    expect(screen.getByText("12.345678, 77.594600")).toBeInTheDocument();
    mouseOut();
    expect(screen.queryByText("12.345678, 77.594600")).not.toBeInTheDocument();
  });
});
