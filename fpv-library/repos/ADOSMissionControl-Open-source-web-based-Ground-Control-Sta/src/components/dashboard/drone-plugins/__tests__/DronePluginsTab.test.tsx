/**
 * @license GPL-3.0-only
 *
 * Render tests for DronePluginsTab. Covers the header, the install
 * button, the empty state for drones with zero plugins, and the
 * unknown-drone fallback.
 */

import { describe, it, expect, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { render } from "@testing-library/react";
import messages from "../../../../../locales/en.json";
import type { FleetDrone } from "@/lib/types";

vi.mock("lucide-react", () =>
  new Proxy(
    {},
    {
      get: (_t, name) => {
        if (name === "__esModule") return false;
        return (props: Record<string, unknown>) => (
          <span data-testid={`icon-${String(name)}`} {...props} />
        );
      },
    },
  ),
);

// Empty fleet by default. Tests that need a drone push it through
// the makeDrone helper and pass the result via the mock factory.
const fleetState: { drones: FleetDrone[] } = { drones: [] };
vi.mock("@/stores/fleet-store", () => ({
  useFleetStore: (sel: (s: unknown) => unknown) => sel(fleetState),
}));

// Hide the install button's transitive dependencies (Convex + dialog
// internals) behind a presentational stub. The Tab is what we're
// testing here.
vi.mock("../InstallPluginButton", () => ({
  InstallPluginButton: () => (
    <button data-testid="install-button">install</button>
  ),
}));

vi.mock("../DronePluginsList", () => ({
  DronePluginsList: ({ emptyState }: { emptyState?: React.ReactNode }) => (
    <div data-testid="plugins-list">{emptyState}</div>
  ),
}));

vi.mock("../RegistryPluginGrid", () => ({
  RegistryPluginGrid: () => <div data-testid="registry-grid" />,
}));

import { DronePluginsTab } from "../DronePluginsTab";

function makeDrone(overrides: Partial<FleetDrone> = {}): FleetDrone {
  return {
    id: "test-drone-1",
    name: "Test Drone",
    status: "online",
    connectionState: "connected",
    flightMode: "STABILIZE",
    armState: "disarmed",
    lastHeartbeat: Date.now(),
    healthScore: 100,
    ...overrides,
  } as FleetDrone;
}

function renderTab(agentId: string) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <DronePluginsTab agentId={agentId} />
    </NextIntlClientProvider>,
  );
}

describe("DronePluginsTab", () => {
  it("falls back to a 'not found' message when the agentId is unknown", () => {
    fleetState.drones = [];
    const { getByText } = renderTab("nonexistent");
    expect(getByText(/not found/i)).toBeDefined();
  });

  it("renders the title and at least one install button when the drone exists", () => {
    fleetState.drones = [makeDrone({ id: "drone-1", name: "Skynode" })];
    const { getByText, getAllByTestId } = renderTab("drone-1");
    expect(getByText(/Skynode/)).toBeDefined();
    // The header AND the empty-state both surface an install button,
    // so we assert the count is at least one and not a strict singular.
    expect(getAllByTestId("install-button").length).toBeGreaterThanOrEqual(1);
  });

  it("passes a non-null empty state into the list (so zero plugins still renders)", () => {
    fleetState.drones = [makeDrone({ id: "drone-1" })];
    const { getByText } = renderTab("drone-1");
    // The empty state copy lives under dronePlugins.emptyStateTitle.
    expect(getByText(/No extensions installed/i)).toBeDefined();
  });
});
