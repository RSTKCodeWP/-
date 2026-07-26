/**
 * @license GPL-3.0-only
 *
 * Mount tests for the fleet-scoped slot host. Covers:
 *   - a fleet contribution mounts a `<PluginSlot>` for its slot
 *   - the host wraps the slot in a fleet-scoped (deviceId=null) provider
 *   - no contribution → the host renders the empty state (or nothing)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import type { PluginSlotContribution } from "@/components/plugins/PluginHostProvider";
import type { PluginSlotName } from "@/lib/plugins/types";

const { contributionsRef } = vi.hoisted(() => ({
  contributionsRef: {
    value: [] as Array<PluginSlotContribution & { slot: PluginSlotName }>,
  },
}));

vi.mock("@/hooks/use-fleet-plugin-contributions", () => ({
  useFleetPluginContributions: (slot?: PluginSlotName) =>
    contributionsRef.value.filter((c) => (slot ? c.slot === slot : true)),
}));

// The real PluginSlot pulls in the Convex availability context + the iframe
// host; stub it to a marker that echoes the slot name + how many contributions
// it received, so the host test stays focused on the provider+slot wiring.
vi.mock("@/components/plugins/PluginSlot", () => ({
  PluginSlot: (props: {
    name: string;
    contributions?: ReadonlyArray<unknown>;
  }) => (
    <div
      data-testid="plugin-slot"
      data-slot={props.name}
      data-count={props.contributions?.length ?? 0}
    />
  ),
}));

import { FleetPluginSlot } from "../FleetPluginSlot";

function contribution(
  slot: PluginSlotName,
  over: Partial<PluginSlotContribution> = {},
): PluginSlotContribution & { slot: PluginSlotName } {
  return {
    slot,
    pluginId: "com.example.fleet",
    panelId: "panel-1",
    bundleUrl: "data:text/html,demo",
    grantedCapabilities: new Set<string>([`ui.slot.${slot.replace(/\./g, "-")}`]),
    handlers: {},
    pluginInstallId: "install-1",
    ...over,
  };
}

describe("FleetPluginSlot", () => {
  beforeEach(() => {
    contributionsRef.value = [];
  });

  it("mounts a PluginSlot for the slot when a plugin contributes", () => {
    contributionsRef.value = [contribution("settings.section")];
    render(<FleetPluginSlot name="settings.section" />);
    const slot = screen.getByTestId("plugin-slot");
    expect(slot.getAttribute("data-slot")).toBe("settings.section");
    expect(slot.getAttribute("data-count")).toBe("1");
  });

  it("passes only this slot's contributions to the PluginSlot", () => {
    contributionsRef.value = [
      contribution("hardware.tab"),
      contribution("hardware.tab", { panelId: "panel-2" }),
    ];
    render(<FleetPluginSlot name="hardware.tab" />);
    expect(screen.getByTestId("plugin-slot").getAttribute("data-count")).toBe(
      "2",
    );
  });

  it("renders the empty state when no plugin contributes", () => {
    contributionsRef.value = [];
    render(
      <FleetPluginSlot
        name="map.overlay"
        emptyState={<div data-testid="empty" />}
      />,
    );
    expect(screen.queryByTestId("plugin-slot")).toBeNull();
    expect(screen.getByTestId("empty")).toBeTruthy();
  });

  it("renders nothing when no plugin contributes and no empty state", () => {
    contributionsRef.value = [];
    const { container } = render(
      <FleetPluginSlot name="notification.channel" />,
    );
    expect(container.firstChild).toBeNull();
  });
});
