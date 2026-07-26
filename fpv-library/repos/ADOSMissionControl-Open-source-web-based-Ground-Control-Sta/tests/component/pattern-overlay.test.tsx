import { describe, it, expect, afterEach, vi } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";
import type { ComponentType } from "react";

// Leaflet is imported at module load for a div-icon helper; stub it so jsdom
// never touches the real Leaflet map machinery.
vi.mock("leaflet", () => ({
  default: { divIcon: vi.fn(() => ({})) },
}));

// planner-store (pulled in transitively) persists to IndexedDB — stub the engine.
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn(async () => null),
      setItem: vi.fn(async () => {}),
      removeItem: vi.fn(async () => {}),
    }),
  },
}));

// react-leaflet overlay primitives → inspectable stub elements carrying their
// key props so a test can assert what geometry was drawn.
vi.mock("react-leaflet", async () => {
  const { createElement } = await import("react");
  const make = (testid: string) => (props: Record<string, unknown>) => {
    const opts = props.pathOptions as { dashArray?: string } | undefined;
    return createElement("div", {
      "data-testid": testid,
      "data-radius": props.radius != null ? String(props.radius) : undefined,
      "data-center": props.center ? JSON.stringify(props.center) : undefined,
      "data-positions": props.positions ? JSON.stringify(props.positions) : undefined,
      "data-dash": opts?.dashArray,
    });
  };
  return {
    Polygon: make("rl-polygon"),
    Polyline: make("rl-polyline"),
    Circle: make("rl-circle"),
    CircleMarker: make("rl-circle-marker"),
    Marker: make("rl-marker"),
  };
});

// next/dynamic → resolve the loader and render the (mocked) component.
vi.mock("next/dynamic", async () => {
  const { createElement, useState, useEffect } = await import("react");
  return {
    default: (loader: () => Promise<unknown>) => {
      return function DynamicStub(props: Record<string, unknown>) {
        const [Comp, setComp] = useState<ComponentType<Record<string, unknown>> | null>(null);
        useEffect(() => {
          let alive = true;
          Promise.resolve(loader()).then((mod) => {
            const resolved = (mod as { default?: unknown }).default ?? mod;
            if (alive) setComp(() => resolved as ComponentType<Record<string, unknown>>);
          });
          return () => {
            alive = false;
          };
        }, []);
        return Comp ? createElement(Comp, props) : null;
      };
    },
  };
});

import { usePatternStore } from "@/stores/pattern-store";
import { PatternOverlay } from "@/components/planner/PatternOverlay";

afterEach(() => {
  cleanup();
  usePatternStore.setState({ patternResult: null, appliedBoundary: null });
  usePatternStore.getState().clear();
});

// These tests render the overlay through the async next/dynamic + react-leaflet
// stubs, so the assertions wait on a promise-driven effect. Under full-suite CPU
// contention that async render can occasionally exceed the findBy deadline (it is
// instant in isolation). retry re-runs the (unchanged) geometry assertions so a
// transient timing miss self-heals; a real regression still fails every attempt.
describe("PatternOverlay", { retry: 2, timeout: 15000 }, () => {
  it("renders a coverage ring for a sector-search datum (previously missing overlay)", async () => {
    usePatternStore.setState({
      activePatternType: "sectorSearch",
      sarSectorSearchConfig: { center: [12.97, 77.59], radius: 300, sweeps: 3, altitude: 50, speed: 5, startBearing: 0 },
    });
    render(<PatternOverlay />);
    const circles = await screen.findAllByTestId("rl-circle", {}, { timeout: 5000 });
    expect(circles.some((c) => c.getAttribute("data-radius") === "300")).toBe(true);
  });

  it("renders a coverage rectangle for a parallel-track start point", async () => {
    usePatternStore.setState({
      activePatternType: "parallelTrack",
      sarParallelTrackConfig: { startPoint: [12.97, 77.59], trackLength: 500, trackSpacing: 50, trackCount: 10, bearing: 0, altitude: 50, speed: 5 },
    });
    render(<PatternOverlay />);
    const polys = await screen.findAllByTestId("rl-polygon", {}, { timeout: 5000 });
    const rect = polys.find((p) => JSON.parse(p.getAttribute("data-positions") ?? "[]").length === 4);
    expect(rect).toBeTruthy();
  });

  it("renders a faint applied boundary when no pattern is active", async () => {
    usePatternStore.setState({
      activePatternType: null,
      appliedBoundary: { kind: "circle", center: [12.97, 77.59], radius: 150 },
    });
    render(<PatternOverlay />);
    const circles = await screen.findAllByTestId("rl-circle", {}, { timeout: 5000 });
    const applied = circles.find((c) => c.getAttribute("data-radius") === "150");
    expect(applied).toBeTruthy();
    expect(applied!.getAttribute("data-dash")).toBe("2 6");
  });

  it("hides the applied boundary while a pattern is active", async () => {
    usePatternStore.setState({
      activePatternType: "orbit",
      orbitConfig: { center: [1, 2], radius: 50, direction: "cw", turns: 1, startAngle: 0, altitude: 50, speed: 5 },
      appliedBoundary: { kind: "circle", center: [12.97, 77.59], radius: 150 },
    });
    render(<PatternOverlay />);
    const circles = await screen.findAllByTestId("rl-circle", {}, { timeout: 5000 });
    // The orbit circle renders (radius 50) but the applied outline (radius 150) does not.
    expect(circles.some((c) => c.getAttribute("data-radius") === "50")).toBe(true);
    expect(circles.some((c) => c.getAttribute("data-radius") === "150")).toBe(false);
  });
});
