#!/usr/bin/env node
/**
 * ardudeck-sim-engine - headless flight simulator.
 *
 * Binds one SITL JSON FDM UDP port per vehicle and a single shared state
 * WebSocket. Launch each SITL pointed at us with `--model JSON:<host>`.
 *
 * Usage:
 *   ardudeck-sim-engine [--fdm-port 9002] [--ws-port 9020] [--vehicles 1]
 *                       [--kind copter|plane|rover] [--frame frame.json]
 *                       [--home lat,lng,alt,hdg] [--id v]
 *                       [--wind n,e,d,intensity,tau] [--noise] [--battery]
 */

import { readFileSync } from 'node:fs';
import {
  DEFAULT_ENVIRONMENT,
  CALM_WIND,
  NO_SENSOR_NOISE,
  multirotorParamsFromFrame,
  type MultirotorParams,
  type WindConfig,
  type SensorNoiseConfig,
  type BatteryConfig,
} from '@ardudeck/sim-physics';
import {
  SimVehicle,
  DEFAULT_PLANE_PARAMS,
  DEFAULT_ROVER_PARAMS,
  DEFAULT_FIDELITY,
  batteryFromFrame,
  type FidelityConfig,
  type HomeLocation,
  type VehicleKind,
} from './vehicle.js';
import { DEFAULT_FDM_PORT } from './json-fdm.js';
import { SimWorld } from './world.js';

const DEFAULT_WS_PORT = 9020;

const DEFAULT_PARAMS: MultirotorParams = {
  mass: 1.5, diagonalSize: 0.4, numMotors: 4, hoverThrOut: 0.39, propExpo: 0.65,
  pwmMin: 1000, pwmMax: 2000, spinMin: 0.15, spinMax: 0.95, dragCoef: 0.15, yawTorqueCoef: 0.02,
};

function parseArgs(argv: string[]): Map<string, string> {
  const out = new Map<string, string>();
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a && a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith('--')) { out.set(key, next); i++; }
      else out.set(key, 'true');
    }
  }
  return out;
}

function parseHome(s: string | undefined): HomeLocation {
  const def: HomeLocation = { lat: -35.363261, lng: 149.165230, alt: 584, heading: 353 };
  if (!s) return def;
  const p = s.split(',').map((x) => Number(x.trim()));
  return {
    lat: Number.isFinite(p[0]) ? (p[0] as number) : def.lat,
    lng: Number.isFinite(p[1]) ? (p[1] as number) : def.lng,
    alt: Number.isFinite(p[2]) ? (p[2] as number) : def.alt,
    heading: Number.isFinite(p[3]) ? (p[3] as number) : def.heading,
  };
}

function parseWind(s: string | undefined): WindConfig {
  if (!s) return CALM_WIND;
  const p = s.split(',').map((x) => Number(x.trim()));
  return {
    steady: { x: p[0] ?? 0, y: p[1] ?? 0, z: p[2] ?? 0 },
    intensity: p[3] ?? 0,
    timeConstant: p[4] ?? 1,
  };
}

interface LoadedCopter {
  params: MultirotorParams;
  battery?: BatteryConfig;
}

function loadCopter(framePath: string | undefined, wantBattery: boolean): LoadedCopter {
  if (!framePath) return { params: DEFAULT_PARAMS };
  try {
    const raw = JSON.parse(readFileSync(framePath, 'utf-8'));
    const params = multirotorParamsFromFrame(raw);
    const battery = wantBattery ? batteryFromFrame(raw, params.mass * DEFAULT_ENVIRONMENT.gravity) : undefined;
    return { params, battery };
  } catch (err) {
    console.error(`[sim-engine] failed to load frame ${framePath}, using defaults:`, err);
    return { params: DEFAULT_PARAMS };
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const baseFdmPort = Number(args.get('fdm-port') ?? DEFAULT_FDM_PORT);
  const wsPort = Number(args.get('ws-port') ?? DEFAULT_WS_PORT);
  const numVehicles = Math.max(1, Number(args.get('vehicles') ?? 1));
  const kind = (args.get('kind') ?? 'copter') as VehicleKind;
  const baseId = args.get('id') ?? 'v';
  const home = parseHome(args.get('home'));

  const noise: SensorNoiseConfig = args.has('noise')
    ? { gyroNoise: 0.01, accelNoise: 0.05 }
    : NO_SENSOR_NOISE;
  const wind = parseWind(args.get('wind'));
  const wantBattery = args.has('battery');

  const copter = kind === 'copter' ? loadCopter(args.get('frame'), wantBattery) : null;
  const fidelity: FidelityConfig = {
    ...DEFAULT_FIDELITY,
    wind,
    noise,
    battery: copter?.battery,
  };

  const params = kind === 'plane' ? DEFAULT_PLANE_PARAMS : kind === 'rover' ? DEFAULT_ROVER_PARAMS : copter!.params;

  const vehicles = Array.from({ length: numVehicles }, (_, i) => ({
    fdmPort: baseFdmPort + i,
    vehicle: new SimVehicle(`${baseId}${i + 1}`, kind, params, { ...DEFAULT_ENVIRONMENT }, home, fidelity, i + 1),
  }));

  const world = new SimWorld(vehicles, wsPort);
  await world.start();

  console.log(`[sim-engine] ${numVehicles} ${kind}(s), FDM ports ${baseFdmPort}..${baseFdmPort + numVehicles - 1}, state WS ws:${wsPort}`);
  console.log(`[sim-engine] wind=${wind.intensity > 0 ? `${wind.intensity}m/s turb` : 'calm'} noise=${args.has('noise')} battery=${wantBattery}`);
  console.log('[sim-engine] launch SITL with:  --model JSON:127.0.0.1');

  const shutdown = () => { world.stop(); process.exit(0); };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  console.error('[sim-engine] fatal:', err);
  process.exit(1);
});
