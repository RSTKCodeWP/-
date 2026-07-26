/**
 * @license GPL-3.0-only
 *
 * Unit tests for the local-nodes registry identity reconciliation: in-place
 * deviceId migration (re-flash heal) and host de-duplication (re-pair replaces
 * the stale-identity ghost instead of leaving a second offline card).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// The store is persisted; bind a deterministic in-memory localStorage before
// the store module is imported (createJSONStorage resolves the global once).
vi.hoisted(() => {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    writable: true,
    value: {
      getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
      clear: () => mem.clear(),
      key: (i: number) => Array.from(mem.keys())[i] ?? null,
      get length() {
        return mem.size;
      },
    },
  });
});

import { useLocalNodesStore, type LocalNode } from "../local-nodes-store";

function node(over: Partial<LocalNode>): LocalNode {
  return {
    deviceId: "dev",
    name: "Agent",
    hostname: "http://192.168.0.5:8080",
    apiKey: "key",
    profile: "drone",
    pairedAt: 1,
    ...over,
  };
}

function nodes() {
  return useLocalNodesStore.getState().nodes;
}

beforeEach(() => {
  useLocalNodesStore.setState({ nodes: [] });
});

describe("migrateNode", () => {
  it("renames a node's deviceId in place, preserving host/key and applying the patch", () => {
    useLocalNodesStore
      .getState()
      .addNode(node({ deviceId: "old", apiKey: "k1", name: "Rig" }));

    useLocalNodesStore.getState().migrateNode("old", "new", { name: "Rig 2" });

    const list = nodes();
    expect(list).toHaveLength(1);
    expect(list[0].deviceId).toBe("new");
    expect(list[0].apiKey).toBe("k1"); // preserved
    expect(list[0].name).toBe("Rig 2"); // patched
  });

  it("preserves position when migrating a middle node", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "a" }));
    s.addNode(node({ deviceId: "b" }));
    s.addNode(node({ deviceId: "c" }));

    s.migrateNode("b", "b2");

    expect(nodes().map((n) => n.deviceId)).toEqual(["a", "b2", "c"]);
  });

  it("drops a colliding pre-existing node so the migrated node wins", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "old", apiKey: "fresh" }));
    s.addNode(node({ deviceId: "new", apiKey: "stale" }));

    s.migrateNode("old", "new");

    const list = nodes();
    expect(list).toHaveLength(1);
    expect(list[0].deviceId).toBe("new");
    expect(list[0].apiKey).toBe("fresh"); // migrated node, not the collision
  });

  it("is a no-op when the source node is absent", () => {
    useLocalNodesStore.getState().addNode(node({ deviceId: "x" }));
    useLocalNodesStore.getState().migrateNode("absent", "y");
    expect(nodes().map((n) => n.deviceId)).toEqual(["x"]);
  });

  it("applies a patch when old and new ids are identical", () => {
    useLocalNodesStore.getState().addNode(node({ deviceId: "z", name: "old" }));
    useLocalNodesStore.getState().migrateNode("z", "z", { name: "renamed" });
    expect(nodes()[0].name).toBe("renamed");
  });
});

describe("reconcileHost", () => {
  it("drops a different-identity node reachable at the same hostname", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "ghost", hostname: "http://192.168.0.5:8080" }));
    s.addNode(node({ deviceId: "live", hostname: "http://192.168.0.5:8080" }));

    s.reconcileHost({ hostname: "http://192.168.0.5:8080" }, "live");

    expect(nodes().map((n) => n.deviceId)).toEqual(["live"]);
  });

  it("matches a bare IPv4 against a node's full hostname URL", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "ghost", hostname: "http://192.168.0.5:8080" }));
    s.addNode(node({ deviceId: "live", hostname: "http://ados-x.local:8080" }));

    // Pairing the live box by IPv4 should clear the ghost on the same IP.
    s.reconcileHost({ ipv4: "192.168.0.5" }, "live");

    expect(nodes().map((n) => n.deviceId)).toEqual(["live"]);
  });

  it("matches an mDNS host against a node carrying the same mdnsHost", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(
      node({
        deviceId: "ghost",
        hostname: "http://10.0.0.9:8080",
        mdnsHost: "ados-21b0db.local",
      }),
    );
    s.reconcileHost({ mdnsHost: "ados-21b0db.local." }, "live");
    expect(nodes()).toHaveLength(0);
  });

  it("keeps nodes on unrelated hosts", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "other", hostname: "http://192.168.0.99:8080" }));
    s.reconcileHost({ hostname: "http://192.168.0.5:8080" }, "live");
    expect(nodes().map((n) => n.deviceId)).toEqual(["other"]);
  });

  it("never drops the kept node even if it shares the host", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "live", hostname: "http://192.168.0.5:8080" }));
    s.reconcileHost({ hostname: "http://192.168.0.5:8080" }, "live");
    expect(nodes().map((n) => n.deviceId)).toEqual(["live"]);
  });
});

describe("touchLastSeen (presence debounce)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("stamps on the first touch", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "d1" }));
    s.touchLastSeen("d1");
    expect(nodes()[0].lastSeenAt).toBe(1_000_000);
  });

  it("coalesces a second touch within the min interval (no re-render / no write)", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "d1" }));
    s.touchLastSeen("d1");
    const arr1 = nodes();
    vi.setSystemTime(1_000_000 + 5_000); // 5s later — under the 20s min
    s.touchLastSeen("d1");
    const arr2 = nodes();
    // Same array + node reference: the fleet does not re-render, localStorage
    // is not rewritten — the whole-UI jitter fix.
    expect(arr2).toBe(arr1);
    expect(arr2[0].lastSeenAt).toBe(1_000_000);
  });

  it("stamps again once the min interval has elapsed", () => {
    const s = useLocalNodesStore.getState();
    s.addNode(node({ deviceId: "d1" }));
    s.touchLastSeen("d1");
    const arr1 = nodes();
    vi.setSystemTime(1_000_000 + 21_000); // 21s later — past the 20s min
    s.touchLastSeen("d1");
    const arr2 = nodes();
    expect(arr2).not.toBe(arr1); // fresh stamp → new array (stays live)
    expect(arr2[0].lastSeenAt).toBe(1_000_000 + 21_000);
  });
});
