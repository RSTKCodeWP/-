/**
 * @license GPL-3.0-only
 * MissionAdvisories RTL rows: the return-leg terrain advisory only surfaces when
 * home coordinates and terrain elevation are genuinely available, renders the
 * pure module's own messages, and precedes them with a neutral assumed-altitude
 * note (no configured RTL altitude is available in the planner).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn(async () => null),
      setItem: vi.fn(async () => {}),
      removeItem: vi.fn(async () => {}),
    }),
  },
}));

import { MissionAdvisories } from "@/components/planner/MissionAdvisories";
import { useGeofenceStore } from "@/stores/geofence-store";
import { useDroneManager } from "@/stores/drone-manager";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { RingBuffer } from "@/lib/ring-buffer";
import type { Waypoint, HomePositionData } from "@/lib/types";

function wp(
  id: string,
  lat: number,
  lon: number,
  groundElevation?: number,
): Waypoint {
  return { id, lat, lon, alt: 50, command: "WAYPOINT", groundElevation };
}

const noop = () => {};

beforeEach(() => {
  useGeofenceStore.setState({ enabled: false });
  useDroneManager.setState({ getSelectedProtocol: () => null });
  useTelemetryStore.setState({
    homePosition: new RingBuffer<HomePositionData>(12),
  });
});

describe("MissionAdvisories — RTL return terrain", () => {
  it("flags a return leg that clips terrain when home + terrain are known", () => {
    // Home falls back to WP1 (900 m MSL terrain); WP2 sits over 1000 m terrain.
    // The assumed 30 m return altitude (cruise 930 m MSL) is below the 1000 m
    // ridge on the direct leg home, so the module emits an error for WP2.
    const waypoints = [
      wp("a", 12.9716, 77.5946, 900),
      wp("b", 13.0716, 77.5946, 1000),
    ];
    render(<MissionAdvisories waypoints={waypoints} onSelectWaypoint={noop} />);

    expect(
      screen.getByText(/RTL from WP2 would clip terrain/i),
    ).toBeInTheDocument();
    // Neutral assumed-altitude context note precedes the RTL rows.
    expect(screen.getByText("rtl.assumedReturnAltitude")).toBeInTheDocument();
  });

  it("renders no RTL rows when terrain elevation is unknown", () => {
    // No waypoint carries groundElevation → the module returns [] → no RTL rows,
    // even though the always-informative item-count row keeps the panel visible.
    const waypoints = [wp("a", 12.9716, 77.5946), wp("b", 13.0716, 77.5946)];
    render(<MissionAdvisories waypoints={waypoints} onSelectWaypoint={noop} />);

    expect(screen.queryByText(/RTL from/i)).toBeNull();
    expect(screen.queryByText("rtl.assumedReturnAltitude")).toBeNull();
  });

  it("uses the latest telemetry home sample when present", () => {
    const home = new RingBuffer<HomePositionData>(12);
    home.push({ timestamp: Date.now(), lat: 12.9716, lon: 77.5946, alt: 0 });
    useTelemetryStore.setState({ homePosition: home });

    // Home coordinates come from telemetry; the first waypoint supplies the only
    // terrain sample near launch and the distant high waypoint clips the cruise.
    const waypoints = [
      wp("a", 12.9716, 77.5946, 900),
      wp("b", 13.0716, 77.5946, 1000),
    ];
    render(<MissionAdvisories waypoints={waypoints} onSelectWaypoint={noop} />);

    expect(
      screen.getByText(/RTL from WP2 would clip terrain/i),
    ).toBeInTheDocument();
  });
});
