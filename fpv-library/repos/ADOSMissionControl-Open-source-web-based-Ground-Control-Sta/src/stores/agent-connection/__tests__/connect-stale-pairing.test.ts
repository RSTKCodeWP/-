/**
 * @license GPL-3.0-only
 *
 * The connect() failure classifier: when a locally-paired card cannot connect,
 * a reachable-but-different agent at its host yields a `stalePairing` descriptor
 * (re-flashed / unpaired) so the UI offers a truthful re-pair, while a plain
 * unreachable box stays a transient offline. Covers the live "card points at a
 * re-flashed drone" path; the auto-heal migration mechanics are unit-tested on
 * the store (migrateNode) and validated on the rig.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Persisted local-nodes-store: bind an in-memory localStorage before import.
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
      key: () => null,
      get length() {
        return mem.size;
      },
    },
  });
});

// The connect attempt always fails its authenticated status call here (a stale
// key 401s), so the classifier path runs without success-side effects.
vi.mock("@/lib/agent/client", () => ({
  AgentClient: class {
    getStatus() {
      return Promise.reject(new Error("HTTP 401"));
    }
  },
  normaliseSystemResources: (x: unknown) => x,
}));

const probeAgentMock = vi.fn();
vi.mock("@/lib/agent/local-pair-client", () => ({
  probeAgent: (...args: unknown[]) => probeAgentMock(...args),
}));

import { useAgentConnectionStore } from "../index";
import { useLocalNodesStore, type LocalNode } from "../../local-nodes-store";

const HOST = "http://192.168.0.5:8080";

function seedNode(deviceId: string): LocalNode {
  const node: LocalNode = {
    deviceId,
    name: "Rig",
    hostname: HOST,
    apiKey: "stale-key",
    profile: "drone",
    pairedAt: 1,
  };
  useLocalNodesStore.setState({ nodes: [node] });
  return node;
}

beforeEach(() => {
  probeAgentMock.mockReset();
  useLocalNodesStore.setState({ nodes: [] });
  useAgentConnectionStore.setState({
    connected: false,
    stalePairing: null,
    connectionError: null,
    client: null,
    agentUrl: null,
    nodeDeviceId: null,
    cloudMode: false,
  });
  // The no-IPv4 fallback path pokes /api/lan-pair/discover; deny it so the
  // connect falls straight through to the failure classifier.
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("no net")));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("connect() stale-pairing classification", () => {
  it("flags a re-flashed box (reachable, different device id) as reidentified", async () => {
    seedNode("00025ad5");
    probeAgentMock.mockResolvedValue({ deviceId: "21b0db85", paired: true });

    await useAgentConnectionStore.getState().connect(HOST, "stale-key", "00025ad5");

    const s = useAgentConnectionStore.getState();
    expect(s.connected).toBe(false);
    expect(s.stalePairing).toEqual({
      reason: "reidentified",
      host: HOST,
      deviceId: "00025ad5",
      liveDeviceId: "21b0db85",
    });
    // The card is kept so the operator can act on the prompt.
    expect(useLocalNodesStore.getState().nodes).toHaveLength(1);
  });

  it("flags an unpaired agent (same id, paired:false) as unpaired", async () => {
    seedNode("00025ad5");
    probeAgentMock.mockResolvedValue({ deviceId: "00025ad5", paired: false });

    await useAgentConnectionStore.getState().connect(HOST, "stale-key", "00025ad5");

    const s = useAgentConnectionStore.getState();
    expect(s.connected).toBe(false);
    expect(s.stalePairing?.reason).toBe("unpaired");
  });

  it("stays a transient offline (no stalePairing) when the box is unreachable", async () => {
    seedNode("00025ad5");
    probeAgentMock.mockRejectedValue(new Error("unreachable"));

    await useAgentConnectionStore.getState().connect(HOST, "stale-key", "00025ad5");

    const s = useAgentConnectionStore.getState();
    expect(s.connected).toBe(false);
    expect(s.stalePairing).toBeNull();
    expect(s.connectionError).toBeTruthy();
  });

  it("does not flag stale when the reachable agent still matches and is paired", async () => {
    seedNode("00025ad5");
    // Same id, still paired, but the authenticated call failed (transient 401).
    probeAgentMock.mockResolvedValue({ deviceId: "00025ad5", paired: true });

    await useAgentConnectionStore.getState().connect(HOST, "stale-key", "00025ad5");

    expect(useAgentConnectionStore.getState().stalePairing).toBeNull();
  });
});
