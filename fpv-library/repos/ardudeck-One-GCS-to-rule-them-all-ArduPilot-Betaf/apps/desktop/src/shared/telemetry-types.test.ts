import { describe, it, expect } from 'vitest';
import { getVehicleClass, isVtolClass, ARDUPILOT_COMMON_MODES } from './telemetry-types';

/**
 * Regression guard for the "3D Sim World shows the wrong type + modes for a
 * quadplane" bug. Root cause: a quadplane heartbeats as MAV_TYPE=1 (FIXED_WING)
 * until it reboots and re-evaluates its type, so it is ONLY the Q_ENABLE / SITL
 * frame hints that upgrade it to `vtol`. The detached Sim World window never
 * hydrated those hints, so class detection fell back to `plane`. These tests
 * lock in the hint contract the fix relies on.
 */
describe('getVehicleClass — quadplane reporting FIXED_WING', () => {
  const MAV_TYPE_FIXED_WING = 1;

  it('misdetects as plane when NO hint is present (the pre-fix detached-window state)', () => {
    expect(getVehicleClass(MAV_TYPE_FIXED_WING, {})).toBe('plane');
  });

  it('upgrades to vtol when Q_ENABLE > 0 (the hint the fix restores in detached windows)', () => {
    expect(getVehicleClass(MAV_TYPE_FIXED_WING, { qEnable: 1 })).toBe('vtol');
  });

  it('stays plane when Q_ENABLE is 0 (genuine fixed-wing)', () => {
    expect(getVehicleClass(MAV_TYPE_FIXED_WING, { qEnable: 0 })).toBe('plane');
  });

  it('upgrades to vtol from a known VTOL SITL frame even with Q_ENABLE absent', () => {
    expect(getVehicleClass(MAV_TYPE_FIXED_WING, { sitlFrame: 'quadplane' })).toBe('vtol');
  });

  it('a properly-booted VTOL (MAV_TYPE in the VTOL family) needs no hint', () => {
    expect(getVehicleClass(20, {})).toBe('vtol'); // MAV_TYPE_VTOL_QUADROTOR
  });

  it('the vtol class exposes Q-modes, not the fixed-wing mode set', () => {
    expect(isVtolClass(getVehicleClass(MAV_TYPE_FIXED_WING, { qEnable: 1 }))).toBe(true);
    const vtolModes = ARDUPILOT_COMMON_MODES.vtol.map((m) => m.name);
    // QLOITER/QHOVER-style Q-modes are the hover set a VTOL operator needs and
    // that the plane list lacks.
    expect(vtolModes.some((n) => n.startsWith('Q'))).toBe(true);
    expect(vtolModes).not.toEqual(ARDUPILOT_COMMON_MODES.plane.map((m) => m.name));
  });
});
