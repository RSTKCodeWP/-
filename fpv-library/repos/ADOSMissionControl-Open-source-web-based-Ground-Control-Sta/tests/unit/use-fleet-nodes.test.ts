/**
 * Verifies the useFleetNodes merge + dedup logic. Local-paired nodes
 * shadow cloud entries with the same deviceId, profile + role pass
 * through unchanged, and the merged list sorts by pairedAt ascending.
 *
 * Tests the pure `mergeFleetNodes` function — the hook itself just
 * subscribes to two Zustand stores and forwards the inputs.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { mergeFleetNodes } from "@/hooks/use-fleet-nodes";
import type { PairedDrone } from "@/stores/pairing-store";
import type { LocalNode } from "@/stores/local-nodes-store";

function cloudDrone(overrides: Partial<PairedDrone>): PairedDrone {
  return {
    _id: "convex_default",
    userId: "u",
    deviceId: "default",
    name: "Default",
    apiKey: "k",
    pairedAt: 0,
    ...overrides,
  };
}

function localNode(overrides: Partial<LocalNode>): LocalNode {
  return {
    deviceId: "default",
    name: "Default",
    hostname: "http://default.local:8080",
    apiKey: "k",
    profile: "drone",
    pairedAt: 0,
    ...overrides,
  };
}

describe("mergeFleetNodes", () => {
  it("returns empty when both inputs are empty", () => {
    expect(mergeFleetNodes([], [])).toEqual([]);
  });

  it("renders cloud-only entries with adaptCloud defaults", () => {
    const out = mergeFleetNodes(
      [cloudDrone({ deviceId: "alpha", name: "Alpha", pairedAt: 100 })],
      [],
    );
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      deviceId: "alpha",
      isLocal: false,
      profile: "drone",
    });
  });

  it("propagates cloud profile + role through adaptCloud", () => {
    const out = mergeFleetNodes(
      [
        cloudDrone({
          _id: "convex_gs",
          deviceId: "gs1",
          name: "GS1",
          pairedAt: 100,
          profile: "ground-station",
          role: "relay",
        }),
      ],
      [],
    );
    expect(out[0].profile).toBe("ground-station");
    expect(out[0].role).toBe("relay");
  });

  it("renders local-only entries with isLocal=true and the canonical node: id", () => {
    const out = mergeFleetNodes(
      [],
      [localNode({ deviceId: "beta", name: "Beta", pairedAt: 200 })],
    );
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      deviceId: "beta",
      isLocal: true,
      _id: "node:beta",
    });
  });

  it("keys cloud entries by the canonical node: id and preserves the Convex id on convexId", () => {
    const out = mergeFleetNodes(
      [
        cloudDrone({
          _id: "convex_alpha",
          deviceId: "alpha",
          name: "Alpha",
          pairedAt: 100,
        }),
      ],
      [],
    );
    expect(out).toHaveLength(1);
    expect(out[0]._id).toBe("node:alpha");
    expect(out[0].convexId).toBe("convex_alpha");
  });

  it("locally-paired nodes shadow cloud entries with the same deviceId", () => {
    const out = mergeFleetNodes(
      [
        cloudDrone({
          _id: "convex_gamma",
          deviceId: "gamma",
          name: "Gamma cloud",
          apiKey: "cloud_key",
          pairedAt: 100,
        }),
      ],
      [
        localNode({
          deviceId: "gamma",
          name: "Gamma local",
          apiKey: "local_key",
          hostname: "http://gamma.local:8080",
          pairedAt: 200,
        }),
      ],
    );
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      isLocal: true,
      apiKey: "local_key",
      name: "Gamma local",
    });
  });

  it("sorts the merged list by pairedAt ascending", () => {
    const out = mergeFleetNodes(
      [
        cloudDrone({
          _id: "c2",
          deviceId: "c-late",
          name: "C late",
          pairedAt: 300,
        }),
      ],
      [
        localNode({
          deviceId: "l-early",
          name: "L early",
          hostname: "http://l.local:8080",
          apiKey: "lk",
          profile: "drone",
          pairedAt: 100,
        }),
        localNode({
          deviceId: "l-mid",
          name: "L mid",
          hostname: "http://m.local:8080",
          apiKey: "mk",
          profile: "ground-station",
          role: "direct",
          pairedAt: 200,
        }),
      ],
    );
    expect(out.map((n) => n.deviceId)).toEqual(["l-early", "l-mid", "c-late"]);
  });

  it("local-node profile + role survive adaptLocal unchanged", () => {
    const out = mergeFleetNodes(
      [],
      [
        localNode({
          deviceId: "rx",
          name: "Receiver one",
          hostname: "http://rx.local:8080",
          apiKey: "rxk",
          profile: "ground-station",
          role: "receiver",
          pairedAt: 50,
        }),
      ],
    );
    expect(out[0].profile).toBe("ground-station");
    expect(out[0].role).toBe("receiver");
  });

  it("cloud entry without profile defaults to drone", () => {
    const out = mergeFleetNodes(
      [
        cloudDrone({
          _id: "legacy",
          deviceId: "legacy",
          name: "Legacy",
          pairedAt: 100,
        }),
      ],
      [],
    );
    expect(out[0].profile).toBe("drone");
  });
});
