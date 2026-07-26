/**
 * Maps the desktop `SitlCustomFrame` schema onto the physics engine's
 * `MultirotorParams`. Declared structurally (just the fields we use) so this
 * package stays decoupled from the Electron app - any object with these numeric
 * fields works, including a `SitlCustomFrame`.
 */

import type { MultirotorParams } from './types.js';

export interface FrameLike {
  mass: number;
  diagonal_size: number;
  num_motors: number;
  hoverThrOut: number;
  propExpo: number;
  pwmMin: number;
  pwmMax: number;
  spin_min: number;
  spin_max: number;
  mdrag_coef: number;
}

export function multirotorParamsFromFrame(frame: FrameLike): MultirotorParams {
  return {
    mass: frame.mass,
    diagonalSize: frame.diagonal_size,
    numMotors: frame.num_motors,
    hoverThrOut: frame.hoverThrOut,
    propExpo: frame.propExpo,
    pwmMin: frame.pwmMin,
    pwmMax: frame.pwmMax,
    spinMin: frame.spin_min,
    spinMax: frame.spin_max,
    // Momentum-drag coefficient scaled by mass gives a reasonable linear drag.
    dragCoef: frame.mass * frame.mdrag_coef,
    // Typical multirotor reaction-torque to thrust ratio.
    yawTorqueCoef: 0.02,
  };
}
