import { describe, it, expect } from 'vitest';
import { normalizeHudConfig, unitProfile, resolveHudProfile, DEFAULT_HUD_CONFIG, DEFAULT_POSITIONS, DEFAULT_GROUND_WIDGETS } from './hud-config';

describe('normalizeHudConfig', () => {
  it('fills defaults from an empty/partial config', () => {
    const c = normalizeHudConfig(undefined);
    expect(c.color).toBe('green');
    expect(c.widgets.fpm).toBe(true);
    expect(c.positions.status).toEqual(DEFAULT_POSITIONS.status);
  });

  it('merges partial widgets/positions onto defaults without dropping keys', () => {
    const c = normalizeHudConfig({ color: 'amber', widgets: { fpm: false } as never, positions: { home: { x: 1, y: 2 } } });
    expect(c.color).toBe('amber');
    expect(c.widgets.fpm).toBe(false);
    expect(c.widgets.horizon).toBe(DEFAULT_HUD_CONFIG.widgets.horizon); // untouched key kept
    expect(c.positions.home).toEqual({ x: 1, y: 2 });
    expect(c.positions.battery).toEqual(DEFAULT_POSITIONS.battery);
  });
});

describe('ground profile', () => {
  it('auto resolves rovers and boats to ground, everything else to air', () => {
    expect(resolveHudProfile('auto', 10)).toBe('ground'); // rover
    expect(resolveHudProfile('auto', 11)).toBe('ground'); // surface boat
    expect(resolveHudProfile('auto', 2)).toBe('air'); // quad
    expect(resolveHudProfile('auto', 1)).toBe('air'); // plane
    expect(resolveHudProfile('auto', undefined)).toBe('air');
  });

  it('forced profiles ignore the vehicle type', () => {
    expect(resolveHudProfile('ground', 2)).toBe('ground');
    expect(resolveHudProfile('air', 10)).toBe('air');
  });

  it('ground defaults drop aviation instruments and enable rover readouts', () => {
    expect(DEFAULT_GROUND_WIDGETS.pitchLadder).toBe(false);
    expect(DEFAULT_GROUND_WIDGETS.airspeedTape).toBe(false);
    expect(DEFAULT_GROUND_WIDGETS.altitudeTape).toBe(false);
    expect(DEFAULT_GROUND_WIDGETS.vsi).toBe(false);
    expect(DEFAULT_GROUND_WIDGETS.fpm).toBe(false);
    expect(DEFAULT_GROUND_WIDGETS.groundSpeed).toBe(true);
    expect(DEFAULT_GROUND_WIDGETS.headingTape).toBe(true);
    expect(DEFAULT_GROUND_WIDGETS.steer).toBe(true);
    expect(DEFAULT_GROUND_WIDGETS.tilt).toBe(true);
    expect(DEFAULT_GROUND_WIDGETS.wpDist).toBe(true);
  });

  it('normalize fills widgetsGround for legacy persisted configs', () => {
    const legacy = { widgets: { fpm: false } } as Parameters<typeof normalizeHudConfig>[0];
    const c = normalizeHudConfig(legacy);
    expect(c.widgetsGround).toEqual(DEFAULT_GROUND_WIDGETS);
    expect(c.profile).toBe('auto');
    expect(c.widgets.fpm).toBe(false);
  });
});

describe('unitProfile', () => {
  it('metric is identity', () => {
    const m = unitProfile('metric');
    expect(m.dist(100)).toBe(100);
    expect(m.speed(15)).toBe(15);
    expect(m.distUnit).toBe('m');
  });
  it('imperial converts metres->feet and m/s->mph', () => {
    const im = unitProfile('imperial');
    expect(im.dist(100)).toBeCloseTo(328.08, 1);
    expect(im.speed(10)).toBeCloseTo(22.37, 1);
    expect(im.distUnit).toBe('ft');
    expect(im.speedUnit).toBe('mph');
  });
});
