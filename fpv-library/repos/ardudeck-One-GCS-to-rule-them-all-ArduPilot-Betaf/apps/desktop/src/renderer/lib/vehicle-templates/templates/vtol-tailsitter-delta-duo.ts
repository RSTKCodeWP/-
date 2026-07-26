import { Triangle } from 'lucide-react';
import type { VehicleTemplate } from '../types.js';
import { batteryParams, airspeedParams, commonSafetyParams, simPhysicsParams, matches } from '../param-helpers.js';

/**
 * Tailsitter Delta Duo — 2 motors on a delta wing, flies vertically for
 * takeoff/landing, tilts forward for efficient cruise. No separate control
 * surfaces beyond elevons; differential thrust provides yaw authority.
 *
 * Key params:
 *  - Q_TAILSIT_ENABLE=1  enables tailsitter logic
 *  - Q_FRAME_CLASS=10    single/coax copter (2-motor tailsitter treated as
 *                         a differential-thrust single-class frame)
 *  - Q_FRAME_TYPE=2      vectored-yaw tailsitter (no tail rotor / no rudder)
 *  - Q_TAILSIT_MOTMX=3   bits for motors 1+2 active in hover
 *  - Elevons on SERVO1/2 (77/78) for pitch/roll authority in forward flight.
 */
export const vtolTailsitterDeltaDuo: VehicleTemplate = {
  slug: 'vtol-tailsitter-delta-duo',
  name: 'Tailsitter Delta Duo',
  description: '2-motor delta-wing tailsitter — compact and efficient',
  icon: Triangle,
  vehicleType: 'vtol',
  category: 'vtol',
  defaults: {
    type: 'vtol',
    wingShape: 'delta',
    vtolStyle: 'tailsitter',
    motorArrangement: 'inline-2',
    vtolMotorCount: 2,
    wingspan: 900,
    stallSpeed: 8,
    transitionSpeed: 11,
    weight: 800,
    batteryCells: 4,
    batteryCapacity: 3000,
    thrustToWeight: 2.5,
  },
  toParams: (p) => [
    { name: 'Q_ENABLE',          value: 1,  reason: 'Enable VTOL',                   requiresReboot: true },
    { name: 'Q_TAILSIT_ENABLE',  value: 1,  reason: 'Tailsitter mode',               requiresReboot: true },
    { name: 'Q_FRAME_CLASS',     value: 10, reason: 'Single/coax for 2-motor tailsitter', requiresReboot: true },
    { name: 'Q_FRAME_TYPE',      value: 2,  reason: 'Vectored yaw (no rudder)',       requiresReboot: true },
    { name: 'Q_TAILSIT_INPUT',   value: 2,  reason: 'Body-frame stick input',         requiresReboot: true },
    { name: 'Q_TAILSIT_MOTMX',   value: 3,  reason: 'Motors 1+2 active in hover' },
    { name: 'Q_TAILSIT_VFGAIN',  value: 0.3, reason: 'Vectored thrust yaw gain' },
    { name: 'Q_TAILSIT_VHGAIN',  value: 0.3, reason: 'Vectored thrust hover gain' },
    // Delta wing elevon mixing — SERVO1 = elevon L, SERVO2 = elevon R
    { name: 'SERVO1_FUNCTION',   value: 77, reason: 'Elevon Left (delta wing)',       requiresReboot: true },
    { name: 'SERVO2_FUNCTION',   value: 78, reason: 'Elevon Right (delta wing)',      requiresReboot: true },
    { name: 'SERVO3_FUNCTION',   value: 33, reason: 'Motor 1 (hover + forward)',      requiresReboot: true },
    { name: 'SERVO4_FUNCTION',   value: 34, reason: 'Motor 2 (hover + forward)',      requiresReboot: true },
    { name: 'MIXING_GAIN',       value: 0.5, reason: 'Elevon mix gain' },
    // Airspeed/transition
    { name: 'Q_TRANSITION_MS',   value: 5000, reason: 'Transition duration (5 s)' },
    { name: 'Q_ASSIST_SPEED',    value: Math.max((p.stallSpeed ?? 8) * 0.9, 3), reason: 'Fixed-wing assist threshold' },
    ...airspeedParams(p),
    ...batteryParams(p),
    ...commonSafetyParams(),
  ],
  toSimParams: (p) => simPhysicsParams(p),
  inferFrom: (m) =>
    (matches(m, 'Q_TAILSIT_ENABLE', 1) +
     matches(m, 'Q_FRAME_CLASS', 10) +
     matches(m, 'SERVO1_FUNCTION', 77)) / 3,
};
