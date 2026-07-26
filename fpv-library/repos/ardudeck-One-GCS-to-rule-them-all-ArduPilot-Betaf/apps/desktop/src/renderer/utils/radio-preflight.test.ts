import { describe, it, expect } from 'vitest';
import { evaluateRadioPreflight, parseArduPilotVersion } from './radio-preflight.js';

function getParamFrom(params: Record<string, number>) {
  return (name: string) => params[name];
}

describe('parseArduPilotVersion', () => {
  it('parses the boot banner', () => {
    expect(parseArduPilotVersion('ArduRover V4.6.3 (3fc7011a)')).toEqual({ major: 4, minor: 6 });
    expect(parseArduPilotVersion('ArduCopter V4.5.7')).toEqual({ major: 4, minor: 5 });
    expect(parseArduPilotVersion('EKF3 IMU0 initialised')).toBeNull();
  });
});

describe('evaluateRadioPreflight', () => {
  it('flags CRSF-only RC_PROTOCOLS and fixes it additively (the 512 case)', () => {
    const checks = evaluateRadioPreflight(getParamFrom({ RC_PROTOCOLS: 512, RSSI_TYPE: 0 }), 'ArduRover V4.6.3');
    const rc = checks.find((c) => c.id === 'rc-over-mavlink')!;
    expect(rc.status).toBe('fail');
    expect(rc.fix).toEqual([{ param: 'RC_PROTOCOLS', value: 512 + 65536 }]);
    const rssi = checks.find((c) => c.id === 'rssi-source')!;
    expect(rssi.status).toBe('fail');
    expect(rssi.fix).toEqual([{ param: 'RSSI_TYPE', value: 5 }]);
    const fw = checks.find((c) => c.id === 'firmware-version')!;
    expect(fw.status).toBe('pass');
  });

  it('passes when MAVLink RC bit already set or protocols set to All', () => {
    expect(
      evaluateRadioPreflight(getParamFrom({ RC_PROTOCOLS: 66048, RSSI_TYPE: 5 }), 'ArduRover V4.6.3').every(
        (c) => c.status === 'pass',
      ),
    ).toBe(true);
    const all = evaluateRadioPreflight(getParamFrom({ RC_PROTOCOLS: 1, RSSI_TYPE: 5 }), 'ArduRover V4.6.3');
    expect(all.find((c) => c.id === 'rc-over-mavlink')!.status).toBe('pass');
  });

  it('reports unknown while params are loading and old firmware as unfixable fail', () => {
    const checks = evaluateRadioPreflight(getParamFrom({}), 'ArduCopter V4.5.7');
    expect(checks.find((c) => c.id === 'rc-over-mavlink')!.status).toBe('unknown');
    const fw = checks.find((c) => c.id === 'firmware-version')!;
    expect(fw.status).toBe('fail');
    expect(fw.fix).toBeNull();
  });
});
