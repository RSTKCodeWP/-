import { Triangle } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const copterY6: VehicleTemplate = {
  slug: 'copter-y6',
  name: 'Y6 (coaxial tri)',
  description: 'Three arms, two motors each (coaxial) — compact redundancy',
  icon: Triangle,
  vehicleType: 'copter',
  category: 'multirotor',
  defaults: {
    type: 'copter',
    motorCount: 6,
    motorArrangement: 'y6',
    frameSize: 450,
    weight: 2000,
    batteryCells: 4,
    batteryCapacity: 5000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS', value: 4, reason: 'OctaQuad / Y6',   requiresReboot: true },
    { name: 'FRAME_TYPE',  value: 10, reason: 'Y6B (coaxial)',    requiresReboot: true },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_CLASS', 4) + matches(m, 'FRAME_TYPE', 10)) / 2,
};
