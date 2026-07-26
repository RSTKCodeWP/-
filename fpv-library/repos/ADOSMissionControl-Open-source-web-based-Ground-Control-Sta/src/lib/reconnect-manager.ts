/**
 * @module reconnect-manager
 * @description Pure-class reconnect state machine with exponential backoff.
 * Handles serial (VID/PID match via getPorts) and WebSocket reconnection.
 * @license GPL-3.0-only
 */

import type { ConnectionMeta } from "@/stores/drone-manager";
import { WebSerialTransport } from "@/lib/protocol/transport/webserial";
import { WebSocketTransport } from "@/lib/protocol/transport/websocket";
import { NetMavlinkTransport } from "@/lib/protocol/transport/net-mavlink";
import { createFcAdapter } from "@/lib/protocol/select-fc-adapter";
import type { DroneProtocol, VehicleInfo } from "@/lib/protocol/types";
import { serialPortManager } from "@/lib/serial-port-manager";
import { useDiagnosticsStore } from "@/stores/diagnostics-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useAgentSystemStore } from "@/stores/agent-system-store";

export type ReconnectState = "idle" | "waiting" | "attempting" | "connected" | "failed";

export interface ReconnectEntry {
  droneId: string;
  droneName: string;
  meta: ConnectionMeta;
  state: ReconnectState;
  attempt: number;
  maxAttempts: number;
}

type StateChangeListener = (entry: ReconnectEntry) => void;
type AddDroneCallback = (
  id: string,
  name: string,
  protocol: DroneProtocol,
  transport: WebSerialTransport | WebSocketTransport | NetMavlinkTransport,
  vehicleInfo: import("@/lib/protocol/types").VehicleInfo,
  meta: ConnectionMeta,
) => void;

const BACKOFF_DELAYS = [500, 1000, 2000, 4000, 5000];
const MAX_ATTEMPTS = 10;

export class ReconnectManager {
  private entries = new Map<string, ReconnectEntry>();
  private timers = new Map<string, ReturnType<typeof setTimeout>>();
  private listeners = new Set<StateChangeListener>();
  private addDroneCallback: AddDroneCallback;

  constructor(addDrone: AddDroneCallback) {
    this.addDroneCallback = addDrone;
  }

  /** Start reconnect cycle for a disconnected drone. */
  startReconnect(droneId: string, droneName: string, meta: ConnectionMeta): void {
    // Cancel existing reconnect for same drone
    this.cancelReconnect(droneId);

    const entry: ReconnectEntry = {
      droneId,
      droneName,
      meta,
      state: "waiting",
      attempt: 0,
      maxAttempts: MAX_ATTEMPTS,
    };
    this.entries.set(droneId, entry);
    this.notify(entry);
    this.scheduleAttempt(droneId);
  }

  /** Cancel an in-progress reconnect. */
  cancelReconnect(droneId: string): void {
    const timer = this.timers.get(droneId);
    if (timer) clearTimeout(timer);
    this.timers.delete(droneId);
    this.entries.delete(droneId);
  }

  /** Cancel all reconnects. */
  cancelAll(): void {
    for (const [id] of this.entries) {
      this.cancelReconnect(id);
    }
  }

  /** Subscribe to state changes. Returns unsubscribe. */
  onStateChange(listener: StateChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Check if any reconnect is active. */
  isReconnecting(): boolean {
    for (const entry of this.entries.values()) {
      if (entry.state === "waiting" || entry.state === "attempting") return true;
    }
    return false;
  }

  private notify(entry: ReconnectEntry): void {
    for (const listener of this.listeners) {
      listener(entry);
    }
  }

  private scheduleAttempt(droneId: string): void {
    const entry = this.entries.get(droneId);
    if (!entry) return;

    const delayIdx = Math.min(entry.attempt, BACKOFF_DELAYS.length - 1);
    const delay = BACKOFF_DELAYS[delayIdx];

    const timer = setTimeout(() => {
      this.attempt(droneId);
    }, delay);
    this.timers.set(droneId, timer);
  }

  private async attempt(droneId: string): Promise<void> {
    const entry = this.entries.get(droneId);
    if (!entry) return;

    entry.attempt++;
    entry.state = "attempting";
    this.notify(entry);

    // Log reconnect attempt to diagnostics
    useDiagnosticsStore.getState().logConnection(
      "reconnect_attempt",
      `Reconnect attempt ${entry.attempt}/${entry.maxAttempts} for ${entry.droneName} (${entry.meta.type})`,
    );
    useDiagnosticsStore.getState().logEvent(
      "reconnect_attempt",
      `Reconnect attempt ${entry.attempt}/${entry.maxAttempts} for ${entry.droneName}`,
    );

    try {
      if (entry.meta.type === "serial") {
        await this.attemptSerial(entry);
      } else if (entry.meta.type === "websocket") {
        await this.attemptWebSocket(entry);
      } else if (entry.meta.type === "udp-proxy" || entry.meta.type === "tcp") {
        await this.attemptNet(entry);
      }

      // Success
      entry.state = "connected";
      this.notify(entry);
      this.timers.delete(droneId);
      this.entries.delete(droneId);
    } catch {
      // Failed
      if (entry.attempt >= entry.maxAttempts) {
        entry.state = "failed";
        this.notify(entry);
        this.timers.delete(droneId);
        this.entries.delete(droneId);
      } else {
        entry.state = "waiting";
        this.notify(entry);
        this.scheduleAttempt(droneId);
      }
    }
  }

  private async attemptSerial(entry: ReconnectEntry): Promise<void> {
    const ports = await serialPortManager.getKnownPorts();
    if (ports.length === 0) throw new Error("No serial ports");

    // Try to match by VID/PID if available
    let matchedPort = ports[0].port;
    if (entry.meta.portVendorId !== undefined && entry.meta.portProductId !== undefined) {
      const match = ports.find(
        (p) => p.vendorId === entry.meta.portVendorId && p.productId === entry.meta.portProductId,
      );
      if (match) matchedPort = match.port;
    }

    const transport = new WebSerialTransport();
    await transport.connectToPort(matchedPort, entry.meta.baudRate || 115200);

    // Re-select the adapter from the FC family detected at first connect so a
    // Betaflight/iNav FC reconnects over MSP instead of always assuming MAVLink.
    const adapter = await createFcAdapter(entry.meta.firmwareType);
    let vehicleInfo: VehicleInfo;
    try {
      vehicleInfo = await adapter.connect(transport);
    } catch (err) {
      // The socket opened but no heartbeat arrived; tear it down so a failed
      // attempt doesn't leak the socket (a UDP-listen leak keeps host:port bound
      // and can wedge the next attempt with EADDRINUSE).
      try {
        await transport.disconnect();
      } catch {
        /* ignore */
      }
      throw err;
    }
    // Reconnect under the ORIGINAL id, not a fresh one. For an agent-owned FC
    // (id `node:<deviceId>`, ownsFleetRow=false) the presence row survives the
    // drop, so a new random id would re-attach as a SECOND standalone row
    // (the duplicate). Re-using the id re-attaches to the same registry node.
    const name = `${vehicleInfo.firmwareVersionString} (${vehicleInfo.vehicleClass})`;

    this.addDroneCallback(entry.droneId, name, adapter, transport, vehicleInfo, entry.meta);
  }

  private async attemptWebSocket(entry: ReconnectEntry): Promise<void> {
    // The agent can rotate its MAVLink WebSocket binding (port change, network
    // move) while we're backing off. Prefer the live URL the agent-connection
    // store currently advertises over the one captured at first disconnect so
    // a rotated port isn't retried stale; fall back to the captured URL when
    // the store has none.
    const liveUrl = useAgentConnectionStore.getState().mavlinkUrl;
    const url = liveUrl ?? entry.meta.url;
    if (!url) throw new Error("No URL for WebSocket reconnect");

    const transport = new WebSocketTransport();
    await transport.connect(url);

    // Prefer the family detected at first connect (a direct WS FC); fall back
    // to the family the agent advertises (an agent-owned FC has no persisted
    // meta variant).
    const adapter = await createFcAdapter(
      entry.meta.firmwareType ??
        useAgentSystemStore.getState().status?.fc_variant,
    );
    let vehicleInfo: VehicleInfo;
    try {
      vehicleInfo = await adapter.connect(transport);
    } catch (err) {
      // The socket opened but no heartbeat arrived; tear it down so a failed
      // attempt doesn't leak the socket (a UDP-listen leak keeps host:port bound
      // and can wedge the next attempt with EADDRINUSE).
      try {
        await transport.disconnect();
      } catch {
        /* ignore */
      }
      throw err;
    }
    // Reconnect under the ORIGINAL id (see attemptSerial) so an agent FC
    // re-attaches to its surviving presence card instead of spawning a
    // duplicate standalone row.
    const name = `${vehicleInfo.firmwareVersionString} (${vehicleInfo.vehicleClass})`;

    // Persist the URL actually dialed so a later disconnect doesn't fall back
    // to the stale captured one.
    this.addDroneCallback(entry.droneId, name, adapter, transport, vehicleInfo, {
      ...entry.meta,
      url,
    });
  }

  private async attemptNet(entry: ReconnectEntry): Promise<void> {
    const { proto, host, port } = entry.meta;
    if (!proto || !host || port === undefined) {
      throw new Error("Incomplete endpoint for UDP/TCP reconnect");
    }
    const transport = new NetMavlinkTransport(proto);
    await transport.connect({
      proto,
      host,
      port,
      mode: entry.meta.mode,
      bridgeUrl: entry.meta.bridgeUrl,
    });

    // Prefer the family detected at first connect (a direct UDP/TCP FC); fall
    // back to the family the agent advertises.
    const adapter = await createFcAdapter(
      entry.meta.firmwareType ??
        useAgentSystemStore.getState().status?.fc_variant,
    );
    let vehicleInfo: VehicleInfo;
    try {
      vehicleInfo = await adapter.connect(transport);
    } catch (err) {
      // The socket opened but no heartbeat arrived; tear it down so a failed
      // attempt doesn't leak the socket (a UDP-listen leak keeps host:port bound
      // and can wedge the next attempt with EADDRINUSE).
      try {
        await transport.disconnect();
      } catch {
        /* ignore */
      }
      throw err;
    }
    // Reconnect under the ORIGINAL id (see attemptSerial) so an agent-attached
    // FC re-attaches to its surviving presence card instead of duplicating.
    const name = `${vehicleInfo.firmwareVersionString} (${vehicleInfo.vehicleClass})`;

    this.addDroneCallback(
      entry.droneId,
      name,
      adapter,
      transport,
      vehicleInfo,
      entry.meta,
    );
  }
}
