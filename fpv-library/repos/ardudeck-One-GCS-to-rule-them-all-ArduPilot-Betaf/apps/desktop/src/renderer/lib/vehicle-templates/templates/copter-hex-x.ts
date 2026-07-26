import { Hexagon } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const copterHexX: VehicleTemplate = {
  slug: 'copter-hex-x',
  name: 'Hexacopter (X)',
  description: 'Six motors — redundancy, heavy lift',
  icon: Hexagon,
  vehicleType: 'copter',
  category: 'multirotor',
  defaults: {
    type: 'copter',
    motorCount: 6,
    motorArrangement: 'hex-x',
    frameSize: 550,
    weight: 2400,
    batteryCells: 6,
    batteryCapacity: 6000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS', value: 2, reason: 'Hexacopter', requiresReboot: true },
    { name: 'FRAME_TYPE',  value: 1, reason: 'X arrangement',    requiresReboot: true },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_CLASS', 2) + matches(m, 'FRAME_TYPE', 1)) / 2,
};
