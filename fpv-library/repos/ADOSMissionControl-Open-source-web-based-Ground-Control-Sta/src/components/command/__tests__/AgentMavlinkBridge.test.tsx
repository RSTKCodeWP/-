/**
 * @license GPL-3.0-only
 *
 * Tests for the AgentMavlinkBridge connection cascade. Authentication is
 * orthogonal to the URL: the bridge dials the raw MAVLink proxy URL for any
 * profile and, when a pairing key is held, attaches a freshly-minted ticket
 * as a WebSocket subprotocol.
 *   - a pairing key is held → a ticket is minted and the raw URL is dialed
 *     with the ticket subprotocol;
 *   - no pairing key (unpaired) → the raw URL is dialed bare (open posture);
 *   - a WebSocket failure falls through to the MQTT relay.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";

interface ConnState {
  mavlinkUrl: string | null;
  connected: boolean;
  nodeDeviceId: string | null;
  agentUrl: string | null;
  cloudDeviceId: string | null;
  apiKey: string | null;
}

// Shared mock state + spies. Declared via vi.hoisted so the hoisted
// vi.mock factories below can reference them safely.
const h = vi.hoisted(() => {
  const conn: { current: ConnState } = {
    current: {
      mavlinkUrl: null,
      connected: false,
      nodeDeviceId: null,
      agentUrl: null,
      cloudDeviceId: null,
      apiKey: null,
    },
  };
  return {
    conn,
    wsConnect:
      vi.fn<(url: string, protocols?: string | string[]) => Promise<void>>(),
    mqttConnect: vi.fn<(deviceId: string) => Promise<void>>(),
    adapterConnect: vi.fn(async () => ({ firmware: "ardupilot" })),
    mintWsTicket: vi.fn<() => Promise<string | null>>(),
    addDrone: vi.fn(),
    removeDrone: vi.fn(),
  };
});

// --- Mocked transports (dynamically imported by the bridge) ----------------

vi.mock("@/lib/protocol/transport/websocket", () => ({
  WebSocketTransport: class {
    readonly type = "websocket" as const;
    connect(url: string, protocols?: string | string[]) {
      return h.wsConnect(url, protocols);
    }
    disconnect() {}
  },
}));
vi.mock("@/lib/protocol/transport/mqtt-mavlink", () => ({
  MqttMavlinkTransport: class {
    connect(deviceId: string) {
      return h.mqttConnect(deviceId);
    }
    disconnect() {}
  },
}));
vi.mock("@/lib/protocol/mavlink-adapter", () => ({
  MAVLinkAdapter: class {
    connect() {
      return h.adapterConnect();
    }
    disconnect() {}
  },
}));

// --- Mocked ticket mint -----------------------------------------------------

vi.mock("@/lib/api/ground-station/ws-ticket", () => ({
  WS_TICKET_PROTOCOL: "ados-ws-ticket",
  mintWsTicket: (...args: unknown[]) => h.mintWsTicket(...(args as [])),
}));

// --- Mocked stores ----------------------------------------------------------

vi.mock("@/stores/agent-connection-store", () => {
  const hook = (sel: (s: ConnState) => unknown) => sel(h.conn.current);
  hook.getState = () => h.conn.current;
  return { useAgentConnectionStore: hook };
});

vi.mock("@/stores/agent-system-store", () => {
  const state = { status: { fc_connected: true, board: { name: "Drone" } } };
  const hook = (sel: (s: typeof state) => unknown) => sel(state);
  hook.getState = () => state;
  return { useAgentSystemStore: hook };
});

vi.mock("@/stores/agent-capabilities-store", () => {
  const hook = (sel: (s: Record<string, unknown>) => unknown) =>
    sel({ mavlinkWsUrlPrev: null });
  return { useAgentCapabilitiesStore: hook };
});

vi.mock("@/stores/drone-manager", () => {
  const state = { drones: new Map(), addDrone: h.addDrone, removeDrone: h.removeDrone };
  const hook = () => state;
  hook.getState = () => state;
  return { useDroneManager: hook };
});

vi.mock("@/stores/fleet-store", () => {
  const state = { drones: [] as unknown[] };
  const hook = () => state;
  hook.getState = () => state;
  return { useFleetStore: hook };
});

import { AgentMavlinkBridge } from "../AgentMavlinkBridge";

const { wsConnect, mqttConnect, mintWsTicket, addDrone } = h;

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  wsConnect.mockResolvedValue(undefined);
  mqttConnect.mockResolvedValue(undefined);
  mintWsTicket.mockResolvedValue("tok-xyz");
  h.conn.current = {
    mavlinkUrl: "ws://drone.local:8765/",
    connected: true,
    nodeDeviceId: "dev-1",
    agentUrl: "http://drone.local:8080",
    cloudDeviceId: "cloud-1",
    apiKey: "key-abc",
  };
});

describe("AgentMavlinkBridge connection cascade", () => {
  it("mints a ticket and dials the raw URL with the subprotocol when a key is held", async () => {
    render(<AgentMavlinkBridge />);

    await waitFor(() => expect(addDrone).toHaveBeenCalledTimes(1));
    expect(mintWsTicket).toHaveBeenCalledTimes(1);
    expect(wsConnect).toHaveBeenCalledTimes(1);
    const [url, protocols] = wsConnect.mock.calls[0];
    expect(url).toBe("ws://drone.local:8765/");
    expect(protocols).toEqual(["ados-ws-ticket", "tok-xyz"]);
    expect(mqttConnect).not.toHaveBeenCalled();
  });

  it("dials the raw URL bare with no subprotocol for an unpaired agent", async () => {
    h.conn.current.apiKey = null;
    render(<AgentMavlinkBridge />);

    await waitFor(() => expect(addDrone).toHaveBeenCalledTimes(1));
    expect(mintWsTicket).not.toHaveBeenCalled();
    expect(wsConnect).toHaveBeenCalledTimes(1);
    const [url, protocols] = wsConnect.mock.calls[0];
    expect(url).toBe("ws://drone.local:8765/");
    expect(protocols).toBeUndefined();
  });

  it("falls through to the MQTT relay when every WebSocket dial fails", async () => {
    wsConnect.mockRejectedValue(new Error("refused"));
    render(<AgentMavlinkBridge />);

    await waitFor(() => expect(mqttConnect).toHaveBeenCalledTimes(1));
    // Authenticated + legacy WS both attempted, both rejected.
    expect(wsConnect).toHaveBeenCalledTimes(2);
    expect(mqttConnect).toHaveBeenCalledWith("cloud-1");
    expect(addDrone).toHaveBeenCalledTimes(1);
  });
});
