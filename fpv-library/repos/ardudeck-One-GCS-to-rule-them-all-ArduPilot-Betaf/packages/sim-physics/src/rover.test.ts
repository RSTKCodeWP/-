import { describe, it, expect } from 'vitest';
import { initialRoverState, stepRover, type RoverParams } from './rover.js';
import { DEFAULT_ENVIRONMENT } from './types.js';
import { toEuler } from './math/quat.js';

const params: RoverParams = {
  mass: 5, maxThrust: 40, dragCoef: 4, wheelbase: 0.3, maxSteer: 0.6,
};
const env = DEFAULT_ENVIRONMENT;

function run(pwm: number[], steps: number) {
  let s = initialRoverState();
  for (let i = 0; i < steps; i++) s = stepRover(pwm, s, params, env, 0.02).state;
  return s;
}

describe('rover dynamics', () => {
  it('drives forward under throttle', () => {
    const s = run([1500, 1500, 2000, 1500], 100);
    expect(Math.hypot(s.position.x, s.position.y)).toBeGreaterThan(1);
    expect(s.position.z).toBe(0); // stays on the ground
  });

  it('turns when steering is applied while moving', () => {
    const s = run([2000, 1500, 1800, 1500], 100); // steer + throttle
    expect(Math.abs(toEuler(s.attitude).yaw)).toBeGreaterThan(0.05);
  });

  it('reads ~1g on the accelerometer z-axis (resting on ground)', () => {
    const s = run([1500, 1500, 1500, 1500], 10);
    expect(s.accelBody.z).toBeCloseTo(-env.gravity, 6);
  });

  it('does not turn when stationary', () => {
    const s = run([2000, 1500, 1500, 1500], 50); // full steer, no throttle
    expect(Math.abs(toEuler(s.attitude).yaw)).toBeLessThan(1e-6);
  });
});
