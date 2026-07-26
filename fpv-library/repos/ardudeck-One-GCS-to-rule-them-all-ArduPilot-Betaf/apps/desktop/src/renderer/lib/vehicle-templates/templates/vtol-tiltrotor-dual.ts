import { RotateCw } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, airspeedParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

/**
 * Dual-motor tiltrotor — motors tilt from vertical (hover) to horizontal
 * (cruise). Q_TILT_ENABLE=1, tilt mask picks which motors tilt.
 */
export const vtolTiltrotorDual: VehicleTemplate = {
  slug: 'vtol-tiltrotor-dual',
  name: 'Tiltrotor (dual)',
  description: 'Two motors tilt from hover to cruise — Osprey-style',
  icon: RotateCw,
  vehicleType: 'vtol',
  category: 'vtol',
  defaults: {
    type: 'vtol',
    wingShape: 'standard',
    vtolStyle: 'tiltrotor',
    motorArrangement: 'twin-tractor',
    vtolMotorCount: 2,
    wingspan: 1800,
    stallSpeed: 10,
    transitionSpeed: 14,
    weight: 2500,
    batteryCells: 6,
    batteryCapacity: 8000,
  },
  toParams: (p) => [
    { name: 'Q_ENABLE',        value: 1, reason: 'Enable VTOL',           requiresReboot: true },
    { name: 'Q_TILT_ENABLE',   value: 1, reason: 'Enable tilt servos',    requiresReboot: true },
    { name: 'Q_TILT_MASK',     value: 3, reason: 'Motors 1+2 tilt',        requiresReboot: true },
    { name: 'Q_TILT_TYPE',     value: 0, reason: 'Continuous tilt',        requiresReboot: true },
    { name: 'Q_FRAME_CLASS',   value: 7, reason: 'Bicopter (2-motor tiltrotor)', requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 4,  reason: 'Aileron',     requiresReboot: true },
    { name: 'SERVO2_FUNCTION', value: 19, reason: 'Elevator',    requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 33, reason: 'Motor 1 left',requiresReboot: true },
    { name: 'SERVO4_FUNCTION', value: 34, reason: 'Motor 2 right',requiresReboot: true },
    { name: 'SERVO5_FUNCTION', value: 41, reason: 'Motor 1 tilt', requiresReboot: true },
    { name: 'SERVO6_FUNCTION', value: 42, reason: 'Motor 2 tilt', requiresReboot: true },
    ...airspeedParams(p),
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => (matches(m, 'Q_ENABLE', 1) + matches(m, 'Q_TILT_ENABLE', 1)) / 2,
};
