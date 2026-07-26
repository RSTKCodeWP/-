import { describe, it, expect } from 'vitest';
import {
  MODEL_MAX_OSD_SCREENS,
  RUBY_OSD_ELEMENTS,
  RUBY_OSD_PRESET,
  defaultRubyOsdParams,
  isElementEnabled,
  withElementEnabled,
  applyPreset,
  getFontSize,
  getTransparency,
  serializeOsdBlock,
  parseOsdBlock,
  spliceOsdBlock,
} from './ruby-osd';

describe('RubyFPV OSD element catalog (from flags_osd.h)', () => {
  it('has 5 screens', () => {
    expect(MODEL_MAX_OSD_SCREENS).toBe(5);
  });

  it('maps known elements to the exact source bits', () => {
    const byId = Object.fromEntries(RUBY_OSD_ELEMENTS.map((e) => [e.id, e]));
    // OSD_FLAG_SHOW_ALTITUDE ((u32)0x01<<17)
    expect(byId.altitude).toMatchObject({ field: 'flags', shift: 17 });
    // OSD_FLAG_SHOW_BATTERY ((u32)0x01<<22)
    expect(byId.battery).toMatchObject({ field: 'flags', shift: 22 });
    // OSD_FLAG_SHOW_FLIGHT_MODE_CHANGE ((u32)0x01<<31) - the high bit
    expect(byId.flight_mode_change).toMatchObject({ field: 'flags', shift: 31 });
    // INSTRUMENTS_FLAG_SHOW_HORIZONT ((u32)0x01<<1)
    expect(byId.horizon).toMatchObject({ field: 'instruments', shift: 1 });
    // OSD_FLAG3_SHOW_WIND ((u32)0x01<<4)
    expect(byId.wind).toMatchObject({ field: 'flags3', shift: 4 });
  });

  it('has unique ids and unique (field, shift) pairs with shifts in range', () => {
    const ids = RUBY_OSD_ELEMENTS.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    const pairs = RUBY_OSD_ELEMENTS.map((e) => `${e.field}:${e.shift}`);
    expect(new Set(pairs).size).toBe(pairs.length);
    for (const e of RUBY_OSD_ELEMENTS) {
      expect(e.shift).toBeGreaterThanOrEqual(0);
      expect(e.shift).toBeLessThanOrEqual(31);
    }
  });
});

describe('per-screen element toggles (bitmask, immutable)', () => {
  it('enables and disables an element in the right screen without mutating the input', () => {
    const p0 = defaultRubyOsdParams();
    const p1 = withElementEnabled(p0, 2, 'altitude', true);
    expect(isElementEnabled(p1, 2, 'altitude')).toBe(true);
    expect(isElementEnabled(p1, 0, 'altitude')).toBe(false); // per-screen
    expect(isElementEnabled(p0, 2, 'altitude')).toBe(false); // original untouched

    const p2 = withElementEnabled(p1, 2, 'altitude', false);
    expect(isElementEnabled(p2, 2, 'altitude')).toBe(false);
  });

  it('handles the high bit (shift 31) as an unsigned 32-bit flag', () => {
    const p = withElementEnabled(defaultRubyOsdParams(), 0, 'flight_mode_change', true);
    expect(p.screens[0]!.flags >>> 0).toBe(0x80000000);
    expect(isElementEnabled(p, 0, 'flight_mode_change')).toBe(true);
    expect(serializeOsdBlock(p).includes('2147483648')).toBe(true);
  });
});

describe('osd_preferences packing', () => {
  it('unpacks font size (byte 0) and transparency (byte 1)', () => {
    // font size 3, transparency 2 -> 0x0000_0203
    const prefs = (2 << 8) | 3;
    expect(getFontSize(prefs)).toBe(3);
    expect(getTransparency(prefs)).toBe(2);
  });
});

describe('OSD block serialization (matches models.cpp fprintf, v12)', () => {
  it('writes the header line exactly (osd: screens cur alarmEn alarm altRel gpsPos)', () => {
    const p = defaultRubyOsdParams();
    p.voltageAlarmEnabled = false;
    p.voltageAlarm = 3.3;
    p.altitudeRelative = true;
    p.showGpsPosition = false;
    const first = serializeOsdBlock(p).split('\n')[0];
    expect(first).toBe('osd: 5 0 0 3.300000 1 0');
  });

  it('round-trips serialize -> parse', () => {
    let p = defaultRubyOsdParams();
    p = withElementEnabled(p, 0, 'battery', true);
    p = withElementEnabled(p, 1, 'horizon', true);
    p = withElementEnabled(p, 4, 'flight_mode_change', true);
    p.currentScreen = 2;
    p.uFlags = 5;
    expect(parseOsdBlock(serializeOsdBlock(p))).toEqual(p);
  });
});

describe('splicing the OSD block into a whole model file', () => {
  const model = [
    'ver: 12',
    'someSection: 1 2 3',
    serializeOsdBlock(defaultRubyOsdParams()),
    'nextSection: 9 8 7',
    'END_ST',
  ].join('\n');

  it('replaces only the OSD block and preserves surrounding sections', () => {
    const edited = withElementEnabled(parseOsdBlock(model), 0, 'battery', true);
    const out = spliceOsdBlock(model, edited);
    expect(out).toContain('someSection: 1 2 3');
    expect(out).toContain('nextSection: 9 8 7');
    expect(out).toContain('END_ST');
    // and the new block reads back the edit
    expect(isElementEnabled(parseOsdBlock(out), 0, 'battery')).toBe(true);
  });
});

describe('presets', () => {
  it('exposes the source preset ids', () => {
    expect(RUBY_OSD_PRESET).toMatchObject({ NONE: 0, MINIMAL: 1, COMPACT: 2, DEFAULT: 3, CUSTOM: 4 });
  });

  it('applyPreset selects the element set cumulatively (like models.cpp)', () => {
    const base = defaultRubyOsdParams();

    const none = applyPreset(base, 0, RUBY_OSD_PRESET.NONE);
    expect(isElementEnabled(none, 0, 'battery')).toBe(false);

    const minimal = applyPreset(base, 0, RUBY_OSD_PRESET.MINIMAL);
    expect(isElementEnabled(minimal, 0, 'battery')).toBe(true);
    expect(isElementEnabled(minimal, 0, 'radio_links')).toBe(true);
    expect(isElementEnabled(minimal, 0, 'altitude')).toBe(false); // Compact+ only

    const compact = applyPreset(base, 0, RUBY_OSD_PRESET.COMPACT);
    expect(isElementEnabled(compact, 0, 'altitude')).toBe(true);
    expect(isElementEnabled(compact, 0, 'flight_mode')).toBe(true);
    expect(isElementEnabled(compact, 0, 'battery')).toBe(true); // cumulative
    expect(isElementEnabled(compact, 0, 'distance')).toBe(false); // Default only

    const def = applyPreset(base, 0, RUBY_OSD_PRESET.DEFAULT);
    expect(isElementEnabled(def, 0, 'distance')).toBe(true);
    expect(isElementEnabled(def, 0, 'home')).toBe(true);
    expect(isElementEnabled(def, 0, 'gps_info')).toBe(true);
    expect(isElementEnabled(def, 0, 'ground_speed')).toBe(true);
    expect(isElementEnabled(def, 0, 'cpu_info')).toBe(true); // screens 0-2 only
  });

  it('applyPreset is screen-specific (screens 4-5 skip video/cpu)', () => {
    const def4 = applyPreset(defaultRubyOsdParams(), 4, RUBY_OSD_PRESET.DEFAULT);
    expect(isElementEnabled(def4, 4, 'distance')).toBe(true);
    expect(isElementEnabled(def4, 4, 'cpu_info')).toBe(false);
    expect(isElementEnabled(def4, 4, 'video_mbps')).toBe(false);
  });

  it('CUSTOM preserves the user selection', () => {
    let p = withElementEnabled(defaultRubyOsdParams(), 0, 'wind', true);
    p = applyPreset(p, 0, RUBY_OSD_PRESET.CUSTOM);
    expect(isElementEnabled(p, 0, 'wind')).toBe(true);
    expect(p.screens[0]!.layoutPreset).toBe(RUBY_OSD_PRESET.CUSTOM);
  });
});
