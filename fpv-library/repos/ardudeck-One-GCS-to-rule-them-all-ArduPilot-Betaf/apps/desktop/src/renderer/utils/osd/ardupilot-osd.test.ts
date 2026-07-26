import { describe, it, expect } from 'vitest';
import {
  apOsdParamName,
  resolveApPanel,
  hasArdupilotOsd,
  detectArdupilotOsdScreens,
  readArdupilotOsd,
  buildArdupilotOsdWrites,
  supportedArdupilotElements,
  type OsdParamLike,
} from './ardupilot-osd';

function paramMap(entries: Record<string, number>, type = 9): Map<string, OsdParamLike> {
  const m = new Map<string, OsdParamLike>();
  for (const [k, v] of Object.entries(entries)) m.set(k, { value: v, type });
  return m;
}

// A small but representative ArduPilot OSD param set (screen 1).
const FC = paramMap({
  OSD1_BAT_VOLT_EN: 1,
  OSD1_BAT_VOLT_X: 2,
  OSD1_BAT_VOLT_Y: 1,
  OSD1_ALTITUDE_EN: 0,
  OSD1_ALTITUDE_X: 2,
  OSD1_ALTITUDE_Y: 3,
  OSD1_GSPEED_EN: 1,
  OSD1_GSPEED_X: 1,
  OSD1_GSPEED_Y: 4,
  OSD2_BAT_VOLT_EN: 1,
  OSD2_BAT_VOLT_X: 5,
  OSD2_BAT_VOLT_Y: 5,
});

describe('ArduPilot OSD adapter', () => {
  it('builds canonical param names', () => {
    expect(apOsdParamName(1, 'BAT_VOLT', 'EN')).toBe('OSD1_BAT_VOLT_EN');
    expect(apOsdParamName(3, 'GSPEED', 'X')).toBe('OSD3_GSPEED_X');
  });

  it('resolves panel aliases against the live param set', () => {
    expect(resolveApPanel('battery_voltage', 1, FC)).toBe('BAT_VOLT');
    // Element with no param on this board resolves to null.
    expect(resolveApPanel('esc_rpm', 1, FC)).toBeNull();
  });

  it('detects OSD presence and screens', () => {
    expect(hasArdupilotOsd(FC)).toBe(true);
    expect(detectArdupilotOsdScreens(FC)).toEqual([1, 2]);
    expect(hasArdupilotOsd(paramMap({ ATC_RAT_RLL_P: 0.1 }))).toBe(false);
  });

  it('reads layout only for supported elements', () => {
    const { positions, resolved } = readArdupilotOsd(FC, 1);
    expect(resolved).toBe(3);
    expect(positions.battery_voltage).toEqual({ x: 2, y: 1, enabled: true });
    expect(positions.altitude).toEqual({ x: 2, y: 3, enabled: false });
    expect(positions.speed).toEqual({ x: 1, y: 4, enabled: true });
    expect(positions.esc_rpm).toBeUndefined();
  });

  it('round-trips read -> write for a screen', () => {
    const { positions } = readArdupilotOsd(FC, 1);
    // Move battery voltage and disable speed.
    positions.battery_voltage = { x: 10, y: 0, enabled: true };
    positions.speed = { x: 1, y: 4, enabled: false };

    const writes = buildArdupilotOsdWrites(positions, FC, 1);
    const byId = new Map(writes.map((w) => [w.paramId, w.value]));
    expect(byId.get('OSD1_BAT_VOLT_X')).toBe(10);
    expect(byId.get('OSD1_BAT_VOLT_Y')).toBe(0);
    expect(byId.get('OSD1_BAT_VOLT_EN')).toBe(1);
    expect(byId.get('OSD1_GSPEED_EN')).toBe(0);
  });

  it('never emits writes for params absent on the board', () => {
    const layout = { esc_rpm: { x: 1, y: 1, enabled: true } };
    expect(buildArdupilotOsdWrites(layout, FC, 1)).toEqual([]);
  });

  it('reuses each param existing on-board type', () => {
    const typed = paramMap({ OSD1_RSSI_EN: 1, OSD1_RSSI_X: 1, OSD1_RSSI_Y: 1 }, 6);
    const writes = buildArdupilotOsdWrites({ rssi: { x: 3, y: 3, enabled: true } }, typed, 1);
    expect(writes.every((w) => w.type === 6)).toBe(true);
  });

  it('lists supported elements for greying out', () => {
    const supported = supportedArdupilotElements(FC, 1);
    expect(supported.has('battery_voltage')).toBe(true);
    expect(supported.has('speed')).toBe(true);
    expect(supported.has('esc_rpm')).toBe(false);
  });
});
