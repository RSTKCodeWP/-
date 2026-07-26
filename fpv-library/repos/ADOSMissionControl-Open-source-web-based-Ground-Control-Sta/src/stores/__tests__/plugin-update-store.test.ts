/**
 * @license GPL-3.0-only
 *
 * Unit tests for the plugin update Zustand store. Covers addUpdate,
 * dedupe semantics on (deviceId, pluginId), clearUpdate, clearForDevice,
 * and getUpdatesForDevice.
 */

import { describe, it, expect, beforeEach } from "vitest";

import {
  usePluginUpdateStore,
  type PluginUpdateEvent,
} from "../plugin-update-store";

function makeEvent(overrides: Partial<PluginUpdateEvent> = {}): PluginUpdateEvent {
  return {
    deviceId: "drone-1",
    pluginId: "plugin-a",
    currentVersion: "1.0.0",
    latestVersion: "2.0.0",
    reason: "major_bump",
    newPermissions: [],
    timestamp: 1_000,
    ...overrides,
  };
}

describe("plugin-update-store", () => {
  beforeEach(() => {
    usePluginUpdateStore.setState({ pendingUpdates: [] });
  });

  it("addUpdate appends an event when no prior entry exists", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent());
    expect(usePluginUpdateStore.getState().pendingUpdates).toHaveLength(1);
  });

  it("addUpdate dedupes by (deviceId, pluginId)", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ timestamp: 1 }));
    usePluginUpdateStore.getState().addUpdate(
      makeEvent({ timestamp: 2, latestVersion: "3.0.0" }),
    );
    const updates = usePluginUpdateStore.getState().pendingUpdates;
    expect(updates).toHaveLength(1);
    expect(updates[0].latestVersion).toBe("3.0.0");
    expect(updates[0].timestamp).toBe(2);
  });

  it("addUpdate keeps events for different plugins on the same device", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ pluginId: "a" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ pluginId: "b" }));
    expect(usePluginUpdateStore.getState().pendingUpdates).toHaveLength(2);
  });

  it("addUpdate keeps events for the same plugin on different devices", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d1" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d2" }));
    expect(usePluginUpdateStore.getState().pendingUpdates).toHaveLength(2);
  });

  it("clearUpdate removes only the matching (deviceId, pluginId)", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ pluginId: "a" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ pluginId: "b" }));
    usePluginUpdateStore.getState().clearUpdate("drone-1", "a");
    const remaining = usePluginUpdateStore.getState().pendingUpdates;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].pluginId).toBe("b");
  });

  it("clearForDevice drops every event for the device", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d1", pluginId: "a" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d1", pluginId: "b" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d2", pluginId: "a" }));
    usePluginUpdateStore.getState().clearForDevice("d1");
    const remaining = usePluginUpdateStore.getState().pendingUpdates;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].deviceId).toBe("d2");
  });

  it("getUpdatesForDevice returns the subset scoped to a device", () => {
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d1", pluginId: "a" }));
    usePluginUpdateStore.getState().addUpdate(makeEvent({ deviceId: "d2", pluginId: "a" }));
    const d1Updates = usePluginUpdateStore.getState().getUpdatesForDevice("d1");
    expect(d1Updates).toHaveLength(1);
    expect(d1Updates[0].deviceId).toBe("d1");
  });
});
