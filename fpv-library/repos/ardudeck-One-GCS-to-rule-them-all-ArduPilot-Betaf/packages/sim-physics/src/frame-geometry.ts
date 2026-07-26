/**
 * Motor layouts for X-frame multirotors, matching ArduPilot's AP_MotorsMatrix
 * setup so SITL's roll/pitch/yaw commands map onto the right physical motors.
 *
 * Angles are degrees clockwise from the nose (forward = +x, right = +y). Position
 * is on a circle of radius = diagonalSize / 2. `yawFactor` is +1 for CCW props,
 * -1 for CW, exactly as in AP_MOTORS_MATRIX_YAW_FACTOR_*.
 *
 * Source of truth: ArduPilot/libraries/AP_Motors/AP_MotorsMatrix.cpp
 */

import type { MotorMount } from './types.js';

interface MotorSpec {
  /** Degrees clockwise from the nose. */
  angleDeg: number;
  /** +1 = CCW prop, -1 = CW prop. */
  yawFactor: 1 | -1;
}

const QUAD_X: MotorSpec[] = [
  { angleDeg: 45, yawFactor: 1 },     // MOT_1 front-right CCW
  { angleDeg: -135, yawFactor: 1 },   // MOT_2 back-left   CCW
  { angleDeg: -45, yawFactor: -1 },   // MOT_3 front-left  CW
  { angleDeg: 135, yawFactor: -1 },   // MOT_4 back-right  CW
];

const HEXA_X: MotorSpec[] = [
  { angleDeg: 90, yawFactor: -1 },    // MOT_1 CW
  { angleDeg: -90, yawFactor: 1 },    // MOT_2 CCW
  { angleDeg: -30, yawFactor: -1 },   // MOT_3 CW
  { angleDeg: 150, yawFactor: 1 },    // MOT_4 CCW
  { angleDeg: 30, yawFactor: 1 },     // MOT_5 CCW
  { angleDeg: -150, yawFactor: -1 },  // MOT_6 CW
];

const OCTA_X: MotorSpec[] = [
  { angleDeg: 22.5, yawFactor: 1 },    // MOT_1 CCW
  { angleDeg: -157.5, yawFactor: 1 },  // MOT_2 CCW
  { angleDeg: 67.5, yawFactor: -1 },   // MOT_3 CW
  { angleDeg: 157.5, yawFactor: -1 },  // MOT_4 CW
  { angleDeg: -22.5, yawFactor: -1 },  // MOT_5 CW
  { angleDeg: -112.5, yawFactor: -1 }, // MOT_6 CW
  { angleDeg: -67.5, yawFactor: 1 },   // MOT_7 CCW
  { angleDeg: 112.5, yawFactor: 1 },   // MOT_8 CCW
];

function specToMount(spec: MotorSpec, radius: number): MotorMount {
  const rad = (spec.angleDeg * Math.PI) / 180;
  return {
    position: { x: radius * Math.cos(rad), y: radius * Math.sin(rad), z: 0 },
    yawFactor: spec.yawFactor,
  };
}

/**
 * Build a generic evenly-spaced X layout with alternating spin for motor counts
 * we don't have an explicit ArduPilot table for. Stable and symmetric, but the
 * per-motor channel order is not guaranteed to match firmware.
 */
function genericLayout(numMotors: number): MotorSpec[] {
  const specs: MotorSpec[] = [];
  for (let i = 0; i < numMotors; i++) {
    specs.push({
      angleDeg: (360 / numMotors) * i + 360 / (2 * numMotors),
      yawFactor: i % 2 === 0 ? 1 : -1,
    });
  }
  return specs;
}

/** Motor mounts (positions + yaw factors) for the given motor count and size. */
export function frameGeometry(numMotors: number, diagonalSize: number): MotorMount[] {
  const radius = diagonalSize / 2;
  let specs: MotorSpec[];
  switch (numMotors) {
    case 4: specs = QUAD_X; break;
    case 6: specs = HEXA_X; break;
    case 8: specs = OCTA_X; break;
    default: specs = genericLayout(numMotors); break;
  }
  return specs.map((s) => specToMount(s, radius));
}
