import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/* Phase 6 / gstack-/qa finding: on a browser with NO WebGL, `new maplibregl.Map()` throws
 * synchronously inside MapView's mount effect. With no guard that throw unmounts the WHOLE React
 * tree → a totally blank page (no banner, no list, no video) — confirmed on the headless QA
 * browser and on any locked-down/old GPU visiting the public demo. The map crashing must never
 * take down the coordinator. This test mocks the WebGL failure and asserts MapView degrades to a
 * "map unavailable" placeholder instead of throwing. */

vi.mock("maplibre-gl", () => {
  class FakeMap {
    constructor() {
      throw new Error("Failed to initialize WebGL");
    }
  }
  return {
    default: { Map: FakeMap, addProtocol: vi.fn(), removeProtocol: vi.fn() },
    Map: FakeMap,
    addProtocol: vi.fn(),
    removeProtocol: vi.fn(),
  };
});

afterEach(cleanup);

describe("MapView WebGL-failure resilience", () => {
  it("renders a graceful fallback instead of crashing when the map can't initialize", async () => {
    const { MapView } = await import("./MapView");
    // must NOT throw out of render — a throw here would blank the whole app
    expect(() => render(<MapView />)).not.toThrow();
    // and it shows an honest placeholder, not a blank void
    expect(screen.getByTestId("map-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("map-unavailable").textContent).toMatch(/map/i);
  });
});
