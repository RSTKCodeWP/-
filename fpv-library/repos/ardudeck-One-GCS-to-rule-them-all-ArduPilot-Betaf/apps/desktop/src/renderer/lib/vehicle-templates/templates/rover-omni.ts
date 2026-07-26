import { Car } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

/**
 * Omni-directional rover — 3 or 4 omni wheels, can translate in any direction.
 * FRAME_CLASS=2, FRAME_TYPE selects 3WD or 4WD layout.
 */
export const roverOmni: VehicleTemplate = {
  slug: 'rover-omni',
  name: 'Omni Rover',
  description: 'Omni-directional wheels — can translate sideways',
  icon: Car,
  vehicleType: 'rover',
  category: 'rover',
  defaults: {
    type: 'rover',
    driveType: 'skid',
    wheelbase: 300,
    wheelDiameter: 100,
    weight: 5000,
    maxSpeed: 3,
    batteryCells: 4,
    batteryCapacity: 6000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS', value: 2, reason: 'Omni rover frame', requiresReboot: true },
    { name: 'FRAME_TYPE',  value: 1, reason: '4-wheel omni (X)', requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 73, reason: 'Throttle Front-Left',  requiresReboot: true },
    { name: 'SERVO2_FUNCTION', value: 74, reason: 'Throttle Front-Right', requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 75, reason: 'Throttle Rear-Left',   requiresReboot: true },
    { name: 'SERVO4_FUNCTION', value: 76, reason: 'Throttle Rear-Right',  requiresReboot: true },
    { name: 'WP_SPEED',     value: p.maxSpeed ?? 2, reason: 'Waypoint speed from maxSpeed' },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'FRAME_CLASS', 2) + matches(m, 'SERVO1_FUNCTION', 73)) / 2,
};
