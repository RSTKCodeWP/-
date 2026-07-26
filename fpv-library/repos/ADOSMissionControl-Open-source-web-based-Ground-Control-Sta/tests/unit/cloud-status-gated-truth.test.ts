/**
 * @module cloud-status-gated-truth.test
 * @description Pins that `mapCloudStatus` (the mapping CloudStatusBridge uses
 * to turn a Convex `cmd_droneStatus` row into an `AgentStatus`) forwards the
 * gated MAVLink truth — transportOpen / mavlinkAlive / heartbeatAgeS / fcSource
 * / fcLinkHint — so a cloud-relayed drone reads the same honest FC state the
 * LAN-direct path does.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { mapCloudStatus } from "@/components/command/bridges/status-mapper";

const BASE = {
  deviceId: "abc123",
  version: "0.89.1",
  uptimeSeconds: 100,
  updatedAt: Date.now(),
  fcConnected: false,
  fcPort: "/dev/ttyACM0",
  fcBaud: 115200,
};

describe("mapCloudStatus gated MAVLink truth", () => {
  it("forwards all five gated-truth fields from the cloud row", () => {
    const out = mapCloudStatus({
      ...BASE,
      transportOpen: true,
      mavlinkAlive: false,
      heartbeatAgeS: 12.5,
      fcSource: "serial",
      fcLinkHint: "no_heartbeat",
    });
    expect(out.transport_open).toBe(true);
    expect(out.mavlink_alive).toBe(false);
    expect(out.heartbeat_age_s).toBe(12.5);
    expect(out.fc_source).toBe("serial");
    expect(out.fc_link_hint).toBe("no_heartbeat");
  });

  it("leaves the gated fields undefined when the agent omits them (older agents)", () => {
    const out = mapCloudStatus({ ...BASE });
    expect(out.transport_open).toBeUndefined();
    expect(out.mavlink_alive).toBeUndefined();
    expect(out.heartbeat_age_s).toBeUndefined();
    expect(out.fc_source).toBeUndefined();
    expect(out.fc_link_hint).toBeUndefined();
  });

  it("preserves a null heartbeat age (no HEARTBEAT seen yet) as null", () => {
    const out = mapCloudStatus({ ...BASE, heartbeatAgeS: null });
    expect(out.heartbeat_age_s).toBeNull();
  });

  it("clamps an unknown fcSource to undefined", () => {
    const out = mapCloudStatus({ ...BASE, fcSource: "bogus" });
    expect(out.fc_source).toBeUndefined();
  });
});
