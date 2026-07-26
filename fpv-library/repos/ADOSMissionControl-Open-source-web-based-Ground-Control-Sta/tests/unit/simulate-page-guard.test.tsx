/**
 * @module simulate-page-guard.test
 * @description Guards the Simulate page's non-destructive contract: mounting
 * /simulate must NEVER clear the shared mission store, even when waypoints exist
 * without a saved active plan (an unsaved, still-being-edited mission). It also
 * asserts the calm read-only empty state renders when the mission is empty.
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { Waypoint } from "@/lib/types";

// The mission / planner stores persist via indexedDBStorage; stub the backing
// store so setState does not reach IndexedDB (absent in the test environment).
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn().mockResolvedValue(null),
      setItem: vi.fn().mockResolvedValue(undefined),
      removeItem: vi.fn().mockResolvedValue(undefined),
    }),
  },
}));

// Keep the heavy 3D viewer / panel / library subtrees (Cesium, Leaflet) out of
// the unit test — the page's mount behavior is what matters here.
vi.mock("next/dynamic", () => ({ default: () => () => null }));
vi.mock("@/components/simulation/SimulateLeftPanel", () => ({
  SimulateLeftPanel: () => null,
}));
vi.mock("@/hooks/use-simulation-keyboard", () => ({
  useSimulationKeyboard: () => {},
}));
vi.mock("@/hooks/use-validation-options", () => ({
  useValidationOptions: () => ({}),
}));
vi.mock("@/lib/validation/mission-validator", () => ({
  validateMission: () => ({ errors: [], warnings: [], valid: true }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import SimulatePage from "@/app/simulate/page";
import { useMissionStore } from "@/stores/mission-store";

const messages = {
  simulate: {
    emptyTitle: "Nothing to simulate yet",
    emptyBody: "Plan a mission first, then come back to preview it in 3D.",
    emptyAction: "Plan a mission",
    editPlan: "Edit Plan",
    missionHasErrors: "Mission has {count} errors",
    missionHasWarnings: "Mission has {count} warnings",
  },
};

function renderPage() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SimulatePage />
    </NextIntlClientProvider>
  );
}

function makeWaypoint(id: string, lat: number, lon: number): Waypoint {
  return { id, lat, lon, alt: 50, command: "WAYPOINT" };
}

describe("SimulatePage — non-destructive read-only contract", () => {
  beforeEach(() => {
    // Fresh mission each test (setState is synchronous, independent of the
    // async IndexedDB hydration).
    useMissionStore.setState({
      activeMission: null,
      waypoints: [],
      progress: 0,
      currentWaypoint: 0,
      uploadState: "idle",
    });
  });

  it("does NOT clear the shared mission on mount when waypoints exist without an active plan", () => {
    const wps = [makeWaypoint("a", 12.9, 77.5), makeWaypoint("b", 12.91, 77.51)];
    useMissionStore.setState({ waypoints: wps, activeMission: null });

    act(() => {
      renderPage();
    });

    // The orphaned/unsaved waypoints survive — Simulate is a preview, never a wipe.
    expect(useMissionStore.getState().waypoints).toHaveLength(2);
    expect(useMissionStore.getState().waypoints.map((w) => w.id)).toEqual(["a", "b"]);
  });

  it("renders the calm empty state (not a wipe) when the mission is empty", () => {
    act(() => {
      renderPage();
    });

    expect(screen.getByText("Nothing to simulate yet")).toBeInTheDocument();
    expect(
      screen.getByText("Plan a mission first, then come back to preview it in 3D.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plan a mission" })).toBeInTheDocument();
  });
});
