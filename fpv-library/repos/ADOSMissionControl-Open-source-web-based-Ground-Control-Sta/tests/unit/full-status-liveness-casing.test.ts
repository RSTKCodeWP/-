/**
 * The agent's native status front emits the FC-liveness detail in camelCase
 * (`mavlinkAlive` / `fcLinkHint` / …) while the GCS reads it off
 * `FullStatusResponse` as snake_case. `normalizeFullStatusLiveness` bridges the
 * two at the LAN boundary so the gated MAVLink truth + the FC-link diagnostic
 * hint actually reach the LAN-direct render path (the bench pairs locally).
 *
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import { normalizeFullStatusLiveness } from "@/lib/agent/agent-client/system";
import type { FullStatusResponse } from "@/lib/agent/types";

const base = {
  version: "0.91.0",
  uptime_seconds: 42,
  board: {},
  health: {},
  fc_connected: false,
  fc_port: "/dev/ttyACM0",
  fc_baud: 0,
  services: [],
} as unknown as FullStatusResponse;

describe("normalizeFullStatusLiveness", () => {
  it("lifts the camelCase liveness the native agent emits into snake_case", () => {
    // The native /api/status/full shape: camelCase liveness, no snake siblings.
    const raw = {
      ...base,
      transportOpen: true,
      mavlinkAlive: false,
      heartbeatAgeS: 7.5,
      fcSource: "serial",
      fcLinkHint: "msp_detected",
    } as unknown as FullStatusResponse;

    const out = normalizeFullStatusLiveness(raw);
    expect(out.transport_open).toBe(true);
    expect(out.mavlink_alive).toBe(false);
    expect(out.heartbeat_age_s).toBe(7.5);
    expect(out.fc_source).toBe("serial");
    expect(out.fc_link_hint).toBe("msp_detected");
  });

  it("preserves an explicit null heartbeat age from camelCase", () => {
    const raw = {
      ...base,
      transportOpen: true,
      mavlinkAlive: false,
      heartbeatAgeS: null,
      fcLinkHint: "no_heartbeat",
    } as unknown as FullStatusResponse;

    const out = normalizeFullStatusLiveness(raw);
    expect(out.heartbeat_age_s).toBeNull();
    expect(out.fc_link_hint).toBe("no_heartbeat");
  });

  it("keeps snake_case when an agent already emits it (snake wins)", () => {
    const raw = {
      ...base,
      transport_open: true,
      mavlink_alive: true,
      heartbeat_age_s: 0.4,
      fc_source: "udp",
      fc_link_hint: "none",
      // a stale camelCase sibling must not override the snake value
      mavlinkAlive: false,
    } as unknown as FullStatusResponse;

    const out = normalizeFullStatusLiveness(raw);
    expect(out.mavlink_alive).toBe(true);
    expect(out.fc_source).toBe("udp");
    expect(out.fc_link_hint).toBe("none");
  });

  it("leaves liveness undefined when neither casing is present (older agent)", () => {
    const out = normalizeFullStatusLiveness({ ...base });
    expect(out.transport_open).toBeUndefined();
    expect(out.mavlink_alive).toBeUndefined();
    expect(out.heartbeat_age_s).toBeUndefined();
    expect(out.fc_source).toBeUndefined();
    expect(out.fc_link_hint).toBeUndefined();
  });
});
