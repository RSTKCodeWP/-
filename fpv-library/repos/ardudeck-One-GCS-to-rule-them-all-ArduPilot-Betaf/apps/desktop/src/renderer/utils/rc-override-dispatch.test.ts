import { describe, it, expect } from 'vitest';
import { rcOverrideCall } from './rc-override-dispatch';

describe('rcOverrideCall', () => {
  it('maps the first four channels to sticks for MAVLink', () => {
    expect(rcOverrideCall('mavlink', [1600, 1400, 2000, 1550, 1000, 1000])).toEqual({
      kind: 'mavlink',
      roll: 1600,
      pitch: 1400,
      throttle: 2000,
      yaw: 1550,
    });
  });

  it('defaults missing stick channels sensibly for MAVLink', () => {
    expect(rcOverrideCall('mavlink', [])).toEqual({
      kind: 'mavlink',
      roll: 1500,
      pitch: 1500,
      throttle: 1000,
      yaw: 1500,
    });
  });

  it('sends the full array over MSP for non-MAVLink links', () => {
    const ch = [1500, 1500, 1000, 1500, 1000, 1000];
    expect(rcOverrideCall('msp', ch)).toEqual({ kind: 'msp', channels: ch });
  });

  it('treats an unknown/undefined protocol as MSP (preserves legacy behaviour)', () => {
    const ch = [1500, 1500, 1000, 1500];
    expect(rcOverrideCall(undefined, ch)).toEqual({ kind: 'msp', channels: ch });
  });
});
