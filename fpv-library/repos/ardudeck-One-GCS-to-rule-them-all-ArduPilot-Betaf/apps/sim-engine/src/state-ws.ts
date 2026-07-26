/**
 * WebSocket broadcaster for vehicle state. The desktop renderer (and later the
 * orchestration server) connect here to drive the 3D world, decoupled from the
 * high-rate physics loop: we keep only the latest state per vehicle and push it
 * out at a fixed render-friendly rate.
 */

import { WebSocketServer, type WebSocket } from 'ws';
import { toEuler, type VehicleState } from '@ardudeck/sim-physics';
import type { HomeLocation } from './vehicle.js';

export interface StateMessage {
  type: 'state';
  id: string;
  home: HomeLocation;
  timestamp: number;
  position: [number, number, number];
  velocity: [number, number, number];
  quaternion: [number, number, number, number];
  euler: { roll: number; pitch: number; yaw: number };
  /** Loaded battery voltage (V), when a battery model is active. */
  batteryVoltage?: number;
}

export class StateWebSocketServer {
  private wss: WebSocketServer | null = null;
  private clients = new Set<WebSocket>();
  private latest = new Map<string, StateMessage>();
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private readonly port: number,
    private readonly broadcastHz = 60,
  ) {}

  start(): void {
    const wss = new WebSocketServer({ port: this.port });
    this.wss = wss;
    wss.on('connection', (ws) => {
      this.clients.add(ws);
      // Send a snapshot immediately so a fresh client isn't blank until the next tick.
      for (const msg of this.latest.values()) ws.send(JSON.stringify(msg));
      ws.on('close', () => this.clients.delete(ws));
      ws.on('error', () => this.clients.delete(ws));
    });
    const interval = Math.max(1, Math.round(1000 / this.broadcastHz));
    this.timer = setInterval(() => this.flush(), interval);
  }

  update(id: string, state: VehicleState, home: HomeLocation, batteryVoltage?: number | null): void {
    this.latest.set(id, {
      type: 'state',
      id,
      home,
      timestamp: state.timestamp,
      position: [state.position.x, state.position.y, state.position.z],
      velocity: [state.velocity.x, state.velocity.y, state.velocity.z],
      quaternion: [state.attitude.w, state.attitude.x, state.attitude.y, state.attitude.z],
      euler: toEuler(state.attitude),
      ...(batteryVoltage != null ? { batteryVoltage } : {}),
    });
  }

  private flush(): void {
    if (this.clients.size === 0) return;
    for (const msg of this.latest.values()) {
      const payload = JSON.stringify(msg);
      for (const ws of this.clients) {
        if (ws.readyState === ws.OPEN) ws.send(payload);
      }
    }
  }

  stop(): void {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    for (const ws of this.clients) { try { ws.close(); } catch { /* ignore */ } }
    this.clients.clear();
    if (this.wss) { this.wss.close(); this.wss = null; }
  }
}
