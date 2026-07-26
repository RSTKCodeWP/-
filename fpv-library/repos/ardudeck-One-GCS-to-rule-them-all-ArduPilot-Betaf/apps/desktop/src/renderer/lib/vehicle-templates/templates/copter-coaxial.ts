import { Circle } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

/**
 * Coaxial quad — 8 motors stacked as 4 coaxial pairs, classic rigid industrial frame.
 */
export const copterCoaxial: VehicleTemplate = {
  slug: 'copter-coaxial',
  name: 'Coaxial Quad (X8)',
  description: 'Eight motors in 4 coaxial pairs — industrial workhorse',
  icon: Circle,
  vehicleType: 'copter',
  category: 'multirotor',
  defaults: {
    type: 'copter',
    motorCount: 8,
    motorArrangement: 'coaxial',
    frameSize: 600,
    weight: 5000,
    batteryCells: 6,
    batteryCapacity: 12000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS', value: 4, reason: 'OctaQuad (coaxial X8)', requiresReboot: true },
    { name: 'FRAME_TYPE',  value: 1, reason: 'X arrangement',           requiresReboot: true },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_CLASS', 4) + matches(m, 'FRAME_TYPE', 1)) / 2,
};
