/**
 * UDP server implementing the SITL JSON FDM backend. Binds the FDM port, and on
 * each servo packet from SITL it steps the vehicle physics and replies with the
 * serialized state. SITL paces itself to our replies (lock-step).
 */

import { createSocket, type Socket, type RemoteInfo } from 'node:dgram';
import { parseServoPacket, serializeState } from './json-fdm.js';
import type { SimVehicle } from './vehicle.js';
import type { VehicleState } from '@ardudeck/sim-physics';

export type StateListener = (id: string, state: VehicleState) => void;

/**
 * If a frame count drops by more than this, treat it as a genuine SITL restart
 * (which resets frame_count to ~0) rather than a retransmit or minor reorder.
 */
const RESTART_BACKWARD_MARGIN = 1000;

export class FdmServer {
  private socket: Socket | null = null;
  private lastFrameCount = -1;
  private simTime = 0;
  /** Cached last reply, re-sent verbatim when SITL retransmits a frame. */
  private lastReply: Buffer | null = null;

  constructor(
    private readonly port: number,
    private readonly vehicle: SimVehicle,
    private readonly onState: StateListener,
  ) {}

  start(): Promise<void> {
    return new Promise((resolve, reject) => {
      const socket = createSocket('udp4');
      this.socket = socket;
      socket.on('error', reject);
      socket.on('message', (msg, rinfo) => this.handleMessage(msg, rinfo));
      socket.bind(this.port, () => {
        socket.removeListener('error', reject);
        socket.on('error', (err) => console.error('[fdm] socket error:', err));
        resolve();
      });
    });
  }

  stop(): void {
    if (this.socket) {
      try { this.socket.close(); } catch { /* already closed */ }
      this.socket = null;
    }
  }

  private handleMessage(msg: Buffer, rinfo: RemoteInfo): void {
    const pkt = parseServoPacket(msg);
    if (!pkt) return;

    const fc = pkt.frameCount;

    // Retransmit: SITL re-sends the same frame_count when it thinks our reply
    // was lost (happens under load, GC pauses, or speedup > 1). Re-send the
    // cached state WITHOUT stepping or resetting. Resetting here was the bug
    // that kept the EKF/GPS perpetually re-initialising (never a GPS fix).
    if (fc === this.lastFrameCount && this.lastReply) {
      this.socket?.send(this.lastReply, rinfo.port, rinfo.address);
      return;
    }

    // A large backward jump means SITL actually restarted (frame_count -> ~0).
    if (fc < this.lastFrameCount - RESTART_BACKWARD_MARGIN) {
      this.vehicle.reset();
      this.simTime = 0;
    } else if (fc < this.lastFrameCount) {
      // Minor out-of-order/old packet: ignore it (don't step backwards).
      if (this.lastReply) this.socket?.send(this.lastReply, rinfo.port, rinfo.address);
      return;
    }
    this.lastFrameCount = fc;

    const dt = pkt.frameRate > 0 ? 1 / pkt.frameRate : 1 / 1200;
    this.simTime += dt;
    const state = this.vehicle.step(pkt.pwm, dt);
    state.timestamp = this.simTime;

    const reply = Buffer.from(serializeState(state), 'ascii');
    this.lastReply = reply;
    this.socket?.send(reply, rinfo.port, rinfo.address);

    this.onState(this.vehicle.id, state);
  }
}
