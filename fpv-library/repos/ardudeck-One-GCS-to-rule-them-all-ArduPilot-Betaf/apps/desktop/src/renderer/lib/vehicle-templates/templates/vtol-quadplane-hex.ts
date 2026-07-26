import { Plane } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, airspeedParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

export const vtolQuadplaneHex: VehicleTemplate = {
  slug: 'vtol-quadplane-hex',
  name: 'Hexplane (6 lift)',
  description: 'Fixed-wing plane with 6 vertical lift motors — heavy-lift VTOL',
  icon: Plane,
  vehicleType: 'vtol',
  category: 'vtol',
  defaults: {
    type: 'vtol',
    wingShape: 'standard',
    vtolStyle: 'quadplane',
    motorArrangement: 'hex-x',
    vtolMotorCount: 6,
    wingspan: 2600,
    stallSpeed: 13,
    transitionSpeed: 17,
    weight: 6000,
    batteryCells: 12,
    batteryCapacity: 22000,
  },
  toParams: (p) => [
    { name: 'Q_ENABLE',        value: 1, reason: 'Enable VTOL (quadplane hex)', requiresReboot: true },
    { name: 'Q_FRAME_CLASS',   value: 2, reason: 'Hexacopter lift frame',        requiresReboot: true },
    { name: 'Q_FRAME_TYPE',    value: 1, reason: 'X arrangement',                 requiresReboot: true },
    { name: 'Q_TAILSIT_ENABLE',value: 0, reason: 'Not a tailsitter',              requiresReboot: true },
    { name: 'Q_TILT_ENABLE',   value: 0, reason: 'Not a tiltrotor',               requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 4,  reason: 'Aileron',           requiresReboot: true },
    { name: 'SERVO2_FUNCTION', value: 19, reason: 'Elevator',          requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 70, reason: 'Forward throttle',  requiresReboot: true },
    { name: 'SERVO4_FUNCTION', value: 21, reason: 'Rudder',            requiresReboot: true },
    { name: 'SERVO5_FUNCTION', value: 33, reason: 'Motor 1 (lift)', requiresReboot: true },
    { name: 'SERVO6_FUNCTION', value: 34, reason: 'Motor 2 (lift)', requiresReboot: true },
    { name: 'SERVO7_FUNCTION', value: 35, reason: 'Motor 3 (lift)', requiresReboot: true },
    { name: 'SERVO8_FUNCTION', value: 36, reason: 'Motor 4 (lift)', requiresReboot: true },
    { name: 'SERVO9_FUNCTION', value: 37, reason: 'Motor 5 (lift)', requiresReboot: true },
    { name: 'SERVO10_FUNCTION',value: 38, reason: 'Motor 6 (lift)', requiresReboot: true },
    { name: 'Q_ASSIST_SPEED',  value: Math.max((p.stallSpeed ?? 12) * 0.8, 4), reason: 'VTOL assist below this speed' },
    ...airspeedParams(p),
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) =>
    (matches(m, 'Q_ENABLE', 1) + matches(m, 'Q_FRAME_CLASS', 2)) / 2,
};
