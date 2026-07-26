/**
 * @module fc-link-remediation.test
 * @description Unit tests for `fcLinkRemediation`, the pure helper that turns
 * the agent's `fc_link_hint` into an actionable, i18n-keyed remediation message
 * (or null when there is nothing useful to say).
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { fcLinkRemediation } from "@/lib/agent/mavlink-link";

describe("fcLinkRemediation", () => {
  it("returns the MSP-detected key when the FC speaks MSP, not MAVLink", () => {
    expect(fcLinkRemediation({ fc_link_hint: "msp_detected" })).toEqual({
      key: "fcLink.remediation.mspDetected",
    });
  });

  it("returns the no-heartbeat key with the port interpolated", () => {
    expect(
      fcLinkRemediation({ fc_link_hint: "no_heartbeat", fc_port: "/dev/ttyACM0" }),
    ).toEqual({
      key: "fcLink.remediation.noHeartbeat",
      values: { port: "/dev/ttyACM0" },
    });
  });

  it("falls back to a placeholder port when none is reported", () => {
    expect(fcLinkRemediation({ fc_link_hint: "no_heartbeat" })).toEqual({
      key: "fcLink.remediation.noHeartbeat",
      values: { port: "—" },
    });
    // An empty-string port is treated the same as missing.
    expect(
      fcLinkRemediation({ fc_link_hint: "no_heartbeat", fc_port: "" }),
    ).toEqual({
      key: "fcLink.remediation.noHeartbeat",
      values: { port: "—" },
    });
  });

  it("returns the source-unreachable key when the configured source will not open", () => {
    expect(fcLinkRemediation({ fc_link_hint: "source_unreachable" })).toEqual({
      key: "fcLink.remediation.sourceUnreachable",
    });
  });

  it("returns null when the link is fine or the hint is unrecognised", () => {
    expect(fcLinkRemediation({ fc_link_hint: "none" })).toBeNull();
    expect(fcLinkRemediation({ fc_link_hint: "something_new" })).toBeNull();
    expect(fcLinkRemediation({})).toBeNull();
    expect(fcLinkRemediation(null)).toBeNull();
    expect(fcLinkRemediation(undefined)).toBeNull();
  });
});
