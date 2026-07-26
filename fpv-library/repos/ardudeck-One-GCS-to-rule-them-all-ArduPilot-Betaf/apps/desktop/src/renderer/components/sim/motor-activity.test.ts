import { describe, it, expect } from 'vitest';
import { motorActivity01 } from './SimWorldView';

describe('motorActivity01', () => {
  it('copter reflects motor PWM even at zero throttle (compassmot / motor test)', () => {
    // Disarmed compassmot: VFR throttle 0, but a motor is spun to ~75% via PWM.
    const a = motorActivity01('copter', 0, [1750, 1000, 1000, 1000]);
    expect(a).toBeCloseTo(0.75, 3);
  });

  it('copter takes the strongest output (single-motor test)', () => {
    const a = motorActivity01('copter', 0, [1000, 1000, 2000, 1000]);
    expect(a).toBe(1);
  });

  it('copter ignores disabled / zero channels', () => {
    const a = motorActivity01('copter', 0, [0, 900, 1200, 0]);
    expect(a).toBeCloseTo(0.2, 3);
  });

  it('copter falls back to throttle when no servo data', () => {
    expect(motorActivity01('copter', 50, undefined)).toBeCloseTo(0.5, 3);
  });

  it('vtol behaves like a copter (reads motor PWM)', () => {
    expect(motorActivity01('vtol', 0, [1500, 1000, 1000, 1000])).toBeCloseTo(0.5, 3);
  });

  it('plane rides throttle and ignores control-surface servos', () => {
    // Centered elevons at 1500us must NOT read as half throttle.
    expect(motorActivity01('plane', 0, [1500, 1500, 1500])).toBe(0);
    expect(motorActivity01('plane', 40, [1500, 1500])).toBeCloseTo(0.4, 3);
  });

  it('rover and sub have no props', () => {
    expect(motorActivity01('rover', 80, [2000])).toBeUndefined();
    expect(motorActivity01('sub', 80, [2000])).toBeUndefined();
  });

  it('clamps out-of-range inputs', () => {
    expect(motorActivity01('copter', 0, [2500])).toBe(1); // PWM above 2000
    expect(motorActivity01('plane', 150, undefined)).toBe(1); // throttle above 100
    expect(motorActivity01('plane', -10, undefined)).toBe(0);
  });
});
