import { Car } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const roverAckermann: VehicleTemplate = {
  slug: 'rover-ackermann',
  name: 'Ackermann Rover',
  description: 'Car-style — single throttle, steering servo',
  icon: Car,
  vehicleType: 'rover',
  category: 'rover',
  defaults: {
    type: 'rover',
    driveType: 'ackermann',
    wheelbase: 300,
    wheelDiameter: 100,
    weight: 3000,
    maxSpeed: 10,
    batteryCells: 3,
    batteryCapacity: 5000,
  },
  toParams: (p) => [
    { name: 'FRAME_CLASS',     value: 1,  reason: 'Rover frame',       requiresReboot: true },
    { name: 'FRAME_TYPE',      value: 0,  reason: 'Undefined (Ackermann uses steering)', requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 26, reason: 'Ground steering',   requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 70, reason: 'Throttle',          requiresReboot: true },
    { name: 'WP_SPEED',        value: p.maxSpeed ?? 5, reason: `Waypoint speed from maxSpeed` },
    { name: 'CRUISE_SPEED',    value: (p.maxSpeed ?? 5) * 0.6, reason: `Cruise speed = 60% of max` },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => matches(m, 'SERVO1_FUNCTION', 26),
};
