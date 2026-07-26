/**
 * @license GPL-3.0-only
 *
 * Round-trip tests for the canonical node-id helper. The whole identity
 * unification rests on `nodeIdForDevice` and `deviceIdFromNodeId` being exact
 * inverses, and on `deviceIdFromNodeId` rejecting non-agent ids (`fc:<random>`)
 * so a direct FC is never mistaken for an agent device.
 */

import { describe, it, expect } from "vitest";

import {
  nodeIdForDevice,
  deviceIdFromNodeId,
  resolveNodeId,
} from "../node-id";

describe("nodeIdForDevice / deviceIdFromNodeId", () => {
  it("round-trips a device id", () => {
    expect(nodeIdForDevice("e8db38b4")).toBe("node:e8db38b4");
    expect(deviceIdFromNodeId("node:e8db38b4")).toBe("e8db38b4");
    expect(deviceIdFromNodeId(nodeIdForDevice("abc123"))).toBe("abc123");
  });

  it("trims whitespace when forming the id", () => {
    expect(nodeIdForDevice("  abc  ")).toBe("node:abc");
  });

  it("matches the registry resolveNodeId for a present device id", () => {
    expect(nodeIdForDevice("dev-7")).toBe(resolveNodeId("dev-7"));
  });

  it("returns null for a non-agent (fc:<random>) id", () => {
    const fcId = resolveNodeId(); // fc:<random>
    expect(fcId.startsWith("fc:")).toBe(true);
    expect(deviceIdFromNodeId(fcId)).toBeNull();
  });

  it("returns null for null / empty / malformed ids", () => {
    expect(deviceIdFromNodeId(null)).toBeNull();
    expect(deviceIdFromNodeId(undefined)).toBeNull();
    expect(deviceIdFromNodeId("")).toBeNull();
    expect(deviceIdFromNodeId("node:")).toBeNull();
    expect(deviceIdFromNodeId("local:dev")).toBeNull();
  });
});
