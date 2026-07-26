import { describe, it, expect, afterEach } from 'vitest';
import { createSocket, type Socket } from 'node:dgram';
import { DEFAULT_ENVIRONMENT, type MultirotorParams } from '@ardudeck/sim-physics';
import { FdmServer } from './fdm-server.js';
import { SimVehicle } from './vehicle.js';
import { encodeServoPacket } from './json-fdm.js';

const PORT = 19002;
const params: MultirotorParams = {
  mass: 1.5, diagonalSize: 0.4, numMotors: 4, hoverThrOut: 0.39, propExpo: 0.65,
  pwmMin: 1000, pwmMax: 2000, spinMin: 0.15, spinMax: 0.95, dragCoef: 0.15, yawTorqueCoef: 0.02,
};

let server: FdmServer | null = null;
let client: Socket | null = null;

afterEach(() => {
  server?.stop();
  if (client) { try { client.close(); } catch { /* ignore */ } client = null; }
});

function exchange(sock: Socket, pwm: number[], frameCount: number): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const onMsg = (msg: Buffer) => {
      sock.removeListener('message', onMsg);
      try { resolve(JSON.parse(msg.toString('ascii').trim())); } catch (e) { reject(e); }
    };
    sock.on('message', onMsg);
    sock.send(encodeServoPacket({ frameRate: 400, frameCount, pwm }), PORT, '127.0.0.1');
  });
}

describe('FDM server end-to-end', () => {
  it('replies with state that climbs under full throttle', async () => {
    const vehicle = new SimVehicle('v1', 'copter', params, { ...DEFAULT_ENVIRONMENT }, { lat: 0, lng: 0, alt: 0, heading: 0 });
    server = new FdmServer(PORT, vehicle, () => {});
    await server.start();

    client = createSocket('udp4');
    await new Promise<void>((r) => client!.bind(0, r));

    const full = [2000, 2000, 2000, 2000];
    let last: Record<string, unknown> = {};
    for (let i = 1; i <= 200; i++) {
      last = await exchange(client, full, i);
    }
    const position = last.position as number[];
    expect(position[2]).toBeLessThan(-0.5); // NED down < 0 => climbed
    const imu = last.imu as { accel_body: number[] };
    expect(Number.isFinite(imu.accel_body[2]!)).toBe(true);
  }, 15000);

  it('does NOT reset on a retransmitted frame (preserves sim state)', async () => {
    const vehicle = new SimVehicle('v1', 'copter', params, { ...DEFAULT_ENVIRONMENT }, { lat: 0, lng: 0, alt: 0, heading: 0 });
    server = new FdmServer(PORT, vehicle, () => {});
    await server.start();
    client = createSocket('udp4');
    await new Promise<void>((r) => client!.bind(0, r));

    const full = [2000, 2000, 2000, 2000];
    let last: Record<string, unknown> = {};
    for (let i = 1; i <= 60; i++) last = await exchange(client, full, i);
    const climbed = (last.position as number[])[2]!;
    expect(climbed).toBeLessThan(-0.1); // has climbed off the ground

    // Retransmit frame 60 (same frameCount): must return the SAME state, not a
    // reset to the origin (which the old code did, breaking EKF/GPS).
    const retx = await exchange(client, full, 60);
    expect((retx.position as number[])[2]).toBeCloseTo(climbed, 6);

    // Forward frame keeps climbing from where we were — proves no reset happened.
    const next = await exchange(client, full, 61);
    expect((next.position as number[])[2]!).toBeLessThan(climbed);
  }, 15000);
});
