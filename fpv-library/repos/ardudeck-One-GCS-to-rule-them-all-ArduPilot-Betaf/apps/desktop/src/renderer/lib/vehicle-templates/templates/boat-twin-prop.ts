import { Anchor } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const boatTwinProp: VehicleTemplate = {
  slug: 'boat-twin-prop',
  name: 'Twin-Prop Boat',
  description: 'Two motors — differential thrust steering (no rudder)',
  icon: Anchor,
  vehicleType: 'boat',
  category: 'boat',
  defaults: {
    type: 'boat',
    hullType: 'displacement',
    hullLength: 1500,
    propellerType: 'prop',
    weight: 12000,
    maxSpeed: 6,
    batteryCells: 6,
    batteryCapacity: 20000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS',     value: 1,  reason: 'Boat (rover frame class)', requiresReboot: true },
    { name: 'FRAME_TYPE',      value: 2,  reason: 'Boat',                     requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 73, reason: 'Throttle Left',            requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 74, reason: 'Throttle Right',           requiresReboot: true },
    { name: 'WP_SPEED',        value: p.maxSpeed ?? 3, reason: 'Waypoint speed' },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_TYPE', 2) + matches(m, 'SERVO1_FUNCTION', 73)) / 2,
};
