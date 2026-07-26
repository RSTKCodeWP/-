import { Anchor } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const boatSingleProp: VehicleTemplate = {
  slug: 'boat-single-prop',
  name: 'Single-Prop Boat',
  description: 'Rudder + one motor',
  icon: Anchor,
  vehicleType: 'boat',
  category: 'boat',
  defaults: {
    type: 'boat',
    hullType: 'displacement',
    hullLength: 1200,
    propellerType: 'prop',
    weight: 8000,
    maxSpeed: 5,
    batteryCells: 6,
    batteryCapacity: 15000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS',     value: 1,  reason: 'Boat (rover frame class)', requiresReboot: true },
    { name: 'FRAME_TYPE',      value: 2,  reason: 'Boat',                     requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 26, reason: 'Rudder (ground steering)', requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 70, reason: 'Throttle',                 requiresReboot: true },
    { name: 'WP_SPEED',        value: p.maxSpeed ?? 2, reason: 'Waypoint speed' },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_TYPE', 2) + matches(m, 'SERVO1_FUNCTION', 26)) / 2,
};
