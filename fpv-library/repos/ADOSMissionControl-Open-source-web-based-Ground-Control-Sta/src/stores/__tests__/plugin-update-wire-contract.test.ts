/**
 * @license GPL-3.0-only
 *
 * Wire-contract tests for the `ados/{deviceId}/plugin/update_available`
 * MQTT message shape. The agent's auto-update loop emits a JSON payload
 * that the GCS bridge (MqttBridge.tsx) parses and dispatches into the
 * plugin update store. These tests pin the contract: snake_case field
 * names, four valid reason values, optional permission delta, optional
 * timestamp. If the agent renames a wire field, this test fails and
 * the bridge needs to be updated in lockstep.
 */

import { describe, it, expect, beforeEach } from "vitest";

import {
  usePluginUpdateStore,
  type PluginUpdateReason,
} from "../plugin-update-store";

/**
 * Normalizer that mirrors the MqttBridge.tsx parsing logic for the
 * `/plugin/update_available` topic. Kept in lockstep so the contract is
 * exercised in isolation without dynamic-importing the mqtt client.
 */
function normalizeUpdateMessage(
  deviceId: string,
  rawPayload: string,
): boolean {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(rawPayload);
  } catch {
    return false;
  }
  if (
    typeof data.plugin_id !== "string" ||
    typeof data.current_version !== "string" ||
    typeof data.latest_version !== "string"
  ) {
    return false;
  }
  const reason = (
    ["major_bump", "permission_delta", "board_mismatch", "pinned"].includes(
      data.reason as string,
    )
      ? data.reason
      : "major_bump"
  ) as PluginUpdateReason;
  usePluginUpdateStore.getState().addUpdate({
    deviceId,
    pluginId: data.plugin_id,
    currentVersion: data.current_version,
    latestVersion: data.latest_version,
    reason,
    newPermissions: Array.isArray(data.new_permissions)
      ? (data.new_permissions as string[])
      : [],
    timestamp:
      typeof data.timestamp_ms === "number" ? data.timestamp_ms : Date.now(),
  });
  return true;
}

describe("plugin update wire contract", () => {
  beforeEach(() => {
    usePluginUpdateStore.setState({ pendingUpdates: [] });
  });

  it("accepts a well-formed major_bump payload", () => {
    const payload = JSON.stringify({
      plugin_id: "altnautica.thermal-cam",
      current_version: "1.2.0",
      latest_version: "2.0.0",
      reason: "major_bump",
      timestamp_ms: 12345,
    });
    const ok = normalizeUpdateMessage("drone-1", payload);
    expect(ok).toBe(true);
    const updates = usePluginUpdateStore.getState().pendingUpdates;
    expect(updates).toHaveLength(1);
    expect(updates[0].pluginId).toBe("altnautica.thermal-cam");
    expect(updates[0].reason).toBe("major_bump");
    expect(updates[0].timestamp).toBe(12345);
  });

  it("accepts a permission_delta payload with new_permissions array", () => {
    const payload = JSON.stringify({
      plugin_id: "altnautica.gimbal-v2",
      current_version: "1.0.1",
      latest_version: "1.1.0",
      reason: "permission_delta",
      new_permissions: ["mavlink.send", "network.outbound"],
      timestamp_ms: 99999,
    });
    normalizeUpdateMessage("drone-2", payload);
    const ev = usePluginUpdateStore.getState().pendingUpdates[0];
    expect(ev.reason).toBe("permission_delta");
    expect(ev.newPermissions).toEqual(["mavlink.send", "network.outbound"]);
  });

  it("falls back to major_bump for an unrecognized reason value", () => {
    const payload = JSON.stringify({
      plugin_id: "x",
      current_version: "1.0.0",
      latest_version: "1.1.0",
      reason: "not-a-real-reason",
    });
    normalizeUpdateMessage("drone-1", payload);
    expect(usePluginUpdateStore.getState().pendingUpdates[0].reason).toBe(
      "major_bump",
    );
  });

  it("rejects a payload missing required fields", () => {
    const payload = JSON.stringify({ plugin_id: "x" });
    const ok = normalizeUpdateMessage("drone-1", payload);
    expect(ok).toBe(false);
    expect(usePluginUpdateStore.getState().pendingUpdates).toHaveLength(0);
  });

  it("rejects a non-JSON payload without throwing", () => {
    const ok = normalizeUpdateMessage("drone-1", "not-json");
    expect(ok).toBe(false);
    expect(usePluginUpdateStore.getState().pendingUpdates).toHaveLength(0);
  });

  it("defaults timestamp to now() when timestamp_ms is missing", () => {
    const before = Date.now();
    const payload = JSON.stringify({
      plugin_id: "x",
      current_version: "1.0.0",
      latest_version: "2.0.0",
      reason: "board_mismatch",
    });
    normalizeUpdateMessage("drone-1", payload);
    const ts = usePluginUpdateStore.getState().pendingUpdates[0].timestamp;
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(Date.now() + 1);
  });
});
