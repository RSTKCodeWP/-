/**
 * @license GPL-3.0-only
 *
 * Unit tests for resolveMavlinkUrl: the raw-proxy URL precedence
 * (heartbeat URL → port+lastIp → LAN-host default 8765) plus the
 * `.local` → IPv4 swap. The cascade dials this single URL for any
 * profile and attaches a ticket when a pairing key is held, so there
 * is no separate authenticated endpoint to resolve.
 */

import { describe, it, expect } from "vitest";
import { resolveMavlinkUrl } from "../urls";

describe("resolveMavlinkUrl — raw proxy URL", () => {
  it("prefers the heartbeat-published URL", () => {
    const { url } = resolveMavlinkUrl(
      { mavlinkWsUrl: "ws://10.0.0.5:8765/", lastIp: "10.0.0.5" },
      "drone.local",
    );
    expect(url).toBe("ws://10.0.0.5:8765/");
  });

  it("swaps a .local heartbeat host for the known IPv4", () => {
    const { url } = resolveMavlinkUrl(
      { mavlinkWsUrl: "ws://drone.local:8765/", lastIp: "10.0.0.5" },
      "drone.local",
    );
    expect(url).toBe("ws://10.0.0.5:8765/");
  });

  it("falls back to a port hint + lastIp", () => {
    const { url } = resolveMavlinkUrl(
      { mavlinkWsPort: 9000, lastIp: "10.0.0.5" },
      "drone.local",
    );
    expect(url).toBe("ws://10.0.0.5:9000/");
  });

  it("falls back to the LAN-host default port 8765", () => {
    const { url } = resolveMavlinkUrl({}, "drone.local");
    expect(url).toBe("ws://drone.local:8765/");
  });

  it("returns null when there is no host to derive from", () => {
    const { url } = resolveMavlinkUrl({}, null);
    expect(url).toBeNull();
  });
});
