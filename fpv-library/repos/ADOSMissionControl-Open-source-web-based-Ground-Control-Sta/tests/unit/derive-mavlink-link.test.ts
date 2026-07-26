/**
 * Unit tests for deriveMavlinkLink — the keystone helper that converts the
 * agent's (fc_connected, transport_open, mavlink_alive) into the alive / silent
 * / down state the FC-link surfaces render. It encodes the legacy fallback, the
 * transport_open-from-fc_connected inference, and the "alive only on an explicit
 * fresh heartbeat" rule, so it carries the highest regression risk (it defines
 * what "FC Connected" means).
 *
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import { deriveMavlinkLink } from "@/lib/agent/mavlink-link";

describe("deriveMavlinkLink", () => {
  it("legacy agent (only fc_connected): true → alive, false → down", () => {
    const up = deriveMavlinkLink({ fc_connected: true });
    expect(up.state).toBe("alive");
    expect(up.hasGatedTruth).toBe(false);
    const down = deriveMavlinkLink({ fc_connected: false });
    expect(down.state).toBe("down");
    expect(down.hasGatedTruth).toBe(false);
  });

  it("gated alive: transport_open + mavlink_alive → alive with age", () => {
    const l = deriveMavlinkLink({
      fc_connected: true,
      transport_open: true,
      mavlink_alive: true,
      heartbeat_age_s: 0.5,
    });
    expect(l.state).toBe("alive");
    expect(l.hasGatedTruth).toBe(true);
    expect(l.heartbeatAgeS).toBe(0.5);
  });

  it("gated silent: transport_open + !mavlink_alive → silent", () => {
    const l = deriveMavlinkLink({
      fc_connected: false,
      transport_open: true,
      mavlink_alive: false,
    });
    expect(l.state).toBe("silent");
    expect(l.hasGatedTruth).toBe(true);
  });

  it("gated msp: an identified MSP FC + transport_open + !mavlink_alive → msp (not silent)", () => {
    for (const variant of ["betaflight", "inav"]) {
      const l = deriveMavlinkLink({
        fc_connected: false,
        transport_open: true,
        mavlink_alive: false,
        fc_variant: variant,
      });
      expect(l.state).toBe("msp");
      expect(l.fcVariant).toBe(variant);
    }
  });

  it("mavlink_alive wins over the MSP variant (a live MAVLink link stays alive)", () => {
    const l = deriveMavlinkLink({
      fc_connected: true,
      transport_open: true,
      mavlink_alive: true,
      fc_variant: "betaflight",
    });
    expect(l.state).toBe("alive");
  });

  it("a non-MSP variant + transport_open + !alive stays silent (no false msp)", () => {
    const l = deriveMavlinkLink({
      fc_connected: false,
      transport_open: true,
      mavlink_alive: false,
      fc_variant: "ardupilot",
    });
    expect(l.state).toBe("silent");
  });

  it("gated down: transport closed → down", () => {
    expect(
      deriveMavlinkLink({
        fc_connected: false,
        transport_open: false,
        mavlink_alive: false,
      }).state,
    ).toBe("down");
  });

  it("never infers alive from a stale port-open (mavlink_alive must be explicit)", () => {
    // transport open, no mavlink_alive flag at all → silent, not alive.
    const l = deriveMavlinkLink({ fc_connected: false, transport_open: true });
    expect(l.mavlinkAlive).toBe(false);
    expect(l.state).toBe("silent");
  });

  it("infers transport_open from a gated fc_connected", () => {
    const l = deriveMavlinkLink({ mavlink_alive: false, fc_connected: true });
    expect(l.transportOpen).toBe(true);
    expect(l.state).toBe("silent");
  });

  it("null / undefined status → down", () => {
    expect(deriveMavlinkLink(null).state).toBe("down");
    expect(deriveMavlinkLink(undefined).state).toBe("down");
  });
});
