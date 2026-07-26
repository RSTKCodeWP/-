import { describe, it, expect, afterEach } from 'vitest';
import { createSocket, type Socket } from 'node:dgram';
import WebSocket from 'ws';
import { DEFAULT_ENVIRONMENT, type MultirotorParams } from '@ardudeck/sim-physics';
import { SimWorld } from './world.js';
import { SimVehicle, DEFAULT_FIDELITY } from './vehicle.js';
import { encodeServoPacket } from './json-fdm.js';

const BASE_FDM = 19100;
const WS_PORT = 19120;
const params: MultirotorParams = {
  mass: 1.5, diagonalSize: 0.4, numMotors: 4, hoverThrOut: 0.39, propExpo: 0.65,
  pwmMin: 1000, pwmMax: 2000, spinMin: 0.15, spinMax: 0.95, dragCoef: 0.15, yawTorqueCoef: 0.02,
};
const home = { lat: 0, lng: 0, alt: 0, heading: 0 };

let world: SimWorld | null = null;
const clients: Socket[] = [];

afterEach(() => {
  world?.stop();
  world = null;
  for (const c of clients) { try { c.close(); } catch { /* ignore */ } }
  clients.length = 0;
});

function exchange(sock: Socket, port: number, pwm: number[], frameCount: number): Promise<void> {
  return new Promise((resolve) => {
    const onMsg = () => { sock.removeListener('message', onMsg); resolve(); };
    sock.on('message', onMsg);
    sock.send(encodeServoPacket({ frameRate: 400, frameCount, pwm }), port, '127.0.0.1');
  });
}

describe('SimWorld multi-vehicle', () => {
  it('runs two vehicles on separate FDM ports and streams both over one WS', async () => {
    world = new SimWorld([
      { fdmPort: BASE_FDM, vehicle: new SimVehicle('v1', 'copter', params, { ...DEFAULT_ENVIRONMENT }, home, DEFAULT_FIDELITY, 1) },
      { fdmPort: BASE_FDM + 1, vehicle: new SimVehicle('v2', 'copter', params, { ...DEFAULT_ENVIRONMENT }, home, DEFAULT_FIDELITY, 2) },
    ], WS_PORT);
    await world.start();

    // Collect WS broadcasts.
    const seen = new Set<string>();
    const ws = new WebSocket(`ws://127.0.0.1:${WS_PORT}`);
    ws.on('message', (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'state') seen.add(msg.id);
    });
    await new Promise<void>((r) => ws.on('open', () => r()));

    const c1 = createSocket('udp4'); const c2 = createSocket('udp4');
    clients.push(c1, c2);
    await Promise.all([new Promise<void>((r) => c1.bind(0, r)), new Promise<void>((r) => c2.bind(0, r))]);

    const full = [2000, 2000, 2000, 2000];
    for (let i = 1; i <= 120; i++) {
      await Promise.all([exchange(c1, BASE_FDM, full, i), exchange(c2, BASE_FDM + 1, full, i)]);
    }
    // Let the WS flush at least one tick.
    await new Promise((r) => setTimeout(r, 80));
    ws.close();

    expect(seen.has('v1')).toBe(true);
    expect(seen.has('v2')).toBe(true);
  }, 20000);
});
