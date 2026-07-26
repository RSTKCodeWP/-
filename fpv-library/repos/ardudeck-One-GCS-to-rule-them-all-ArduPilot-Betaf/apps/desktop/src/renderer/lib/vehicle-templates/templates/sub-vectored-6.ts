import { Waves } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

/**
 * Vectored 6-thruster sub — the BlueROV2 reference frame. 4 vectored thrusters
 * for horizontal motion + 2 vertical thrusters for depth.
 */
export const subVectored6: VehicleTemplate = {
  slug: 'sub-vectored-6',
  name: 'Vectored 6-Thruster',
  description: 'BlueROV2-style — 4 vectored + 2 vertical thrusters',
  icon: Waves,
  vehicleType: 'sub',
  category: 'sub',
  defaults: {
    type: 'sub',
    thrusterCount: 6,
    maxDepth: 100,
    buoyancy: 'neutral',
    weight: 11000,
    batteryCells: 4,
    batteryCapacity: 18000,
  },
  toParams: (p) => [
    { name: 'FRAME_CONFIG',    value: 1,  reason: 'Vectored-6 frame',     requiresReboot: true },
    { name: 'SERVO1_FUNCTION', value: 33, reason: 'Motor 1 (Forward-Right Vec)', requiresReboot: true },
    { name: 'SERVO2_FUNCTION', value: 34, reason: 'Motor 2 (Forward-Left Vec)',  requiresReboot: true },
    { name: 'SERVO3_FUNCTION', value: 35, reason: 'Motor 3 (Rear-Right Vec)',    requiresReboot: true },
    { name: 'SERVO4_FUNCTION', value: 36, reason: 'Motor 4 (Rear-Left Vec)',     requiresReboot: true },
    { name: 'SERVO5_FUNCTION', value: 37, reason: 'Motor 5 (Vertical Right)',    requiresReboot: true },
    { name: 'SERVO6_FUNCTION', value: 38, reason: 'Motor 6 (Vertical Left)',     requiresReboot: true },
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) => matches(m, 'FRAME_CONFIG', 1),
};
