import { describe, it, expect } from 'vitest';
import { detectAdapter, ardupilotAdapter, px4Adapter } from './index';

describe('FC adapter detection', () => {
  it('detects ArduPilot from autopilot=3', () => {
    const a = detectAdapter(3);
    expect(a.type).toBe('ardupilot');
  });

  it('detects PX4 from autopilot=12', () => {
    const a = detectAdapter(12);
    expect(a.type).toBe('px4');
  });

  it('defaults to ArduPilot for unknown autopilot', () => {
    expect(detectAdapter(99).type).toBe('ardupilot');
  });
});

describe('ArduPilot adapter (backed by modeStore)', () => {
  it('resolves copter mode names from backend constants', () => {
    expect(ardupilotAdapter.modeName(0, false)).toBe('Stabilize');
    expect(ardupilotAdapter.modeName(5, false)).toBe('Loiter');
    expect(ardupilotAdapter.modeName(6, false)).toBe('RTL');
    expect(ardupilotAdapter.modeName(28, false)).toBe('Turtle');
  });

  it('resolves plane mode names from backend constants', () => {
    expect(ardupilotAdapter.modeName(0, true)).toBe('Manual');
    expect(ardupilotAdapter.modeName(10, true)).toBe('Auto');
    expect(ardupilotAdapter.modeName(11, true)).toBe('RTL');
    expect(ardupilotAdapter.modeName(13, true)).toBe('Takeoff');
    expect(ardupilotAdapter.modeName(26, true)).toBe('Autoland');
  });

  it('returns mode buttons from backend constants', () => {
    const btns = ardupilotAdapter.modeButtons(false);
    expect(btns.length).toBeGreaterThan(0);
    // Button order and names now match backend constants.py COPTER_BTNS_EN
    expect(btns[0]).toEqual([0, 'Stabilize']);
  });

  it('allModes returns FlightMode objects with correct categories', () => {
    const copterModes = ardupilotAdapter.allModes(false);
    expect(copterModes.length).toBeGreaterThan(10);
    expect(copterModes.find((m) => m.name === 'RTL')?.category).toBe('emergency');
    expect(copterModes.find((m) => m.name === 'Brake')?.category).toBe('emergency');
    expect(copterModes.find((m) => m.name === 'Stabilize')?.category).toBe('manual');
    expect(copterModes.find((m) => m.name === 'Auto')?.category).toBe('auto');

    const planeModes = ardupilotAdapter.allModes(true);
    expect(planeModes.find((m) => m.name === 'Q-Stabilize')?.category).toBe('manual');
    expect(planeModes.find((m) => m.name === 'Training')?.category).toBe('manual');
    expect(planeModes.find((m) => m.name === 'RTL')?.category).toBe('emergency');
    expect(planeModes.find((m) => m.name === 'Takeoff')?.category).toBe('auto');
  });

  it('RTL mode IDs', () => {
    expect(ardupilotAdapter.rtlModeId(false)).toBe(6);
    expect(ardupilotAdapter.rtlModeId(true)).toBe(11);
  });
});

describe('PX4 adapter', () => {
  it('resolves PX4 mode names', () => {
    const posctl = 3 << 16; // main=3 (POSCTL)
    expect(px4Adapter.modeName(posctl, false)).toBe('Position');
  });

  it('resolves PX4 auto sub-modes', () => {
    const mission = (4 << 24) | (4 << 16); // sub=4 (MISSION), main=4 (AUTO)
    expect(px4Adapter.modeName(mission, false)).toBe('Mission');
  });

  it('returns mode buttons', () => {
    const btns = px4Adapter.modeButtons(false);
    expect(btns.length).toBeGreaterThan(0);
  });

  it('allModes includes Return mode as emergency', () => {
    const modes = px4Adapter.allModes(false);
    const rtl = modes.find((m) => m.name === 'Return');
    expect(rtl).toBeDefined();
    expect(rtl?.category).toBe('emergency');
  });
});
