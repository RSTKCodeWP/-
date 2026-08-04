import { describe, expect, it } from 'vitest';
import {
  buildLaunchConfig,
  clampUptilt,
  DEFAULT_FPV_UPTILT_DEG,
  LAUNCH_CONFIG_SCHEMA_VERSION,
  parseLaunchConfig,
  serializeLaunchConfig,
} from '../launch-config.js';

const BASE = {
  region: {
    name: 'bar',
    assetPath: '/regions/bar',
    home: { lat: 42.0936, lon: 19.0947 },
  },
  appVersion: '0.1.0',
  now: new Date('2026-08-03T10:00:00.000Z'),
};

describe('buildLaunchConfig', () => {
  it('writes the current schema version and null Phase 2/4 blocks', () => {
    const config = buildLaunchConfig(BASE);
    expect(config.schemaVersion).toBe(LAUNCH_CONFIG_SCHEMA_VERSION);
    expect(config.vehicle).toBeNull();
    expect(config.conditions).toBeNull();
    expect(config.generatedAt).toBe('2026-08-03T10:00:00.000Z');
  });

  it('defaults the uptilt and clamps an out-of-range one', () => {
    expect(buildLaunchConfig(BASE).camera.fpvUptiltDeg).toBe(DEFAULT_FPV_UPTILT_DEG);
    expect(buildLaunchConfig({ ...BASE, fpvUptiltDeg: 900 }).camera.fpvUptiltDeg).toBe(55);
    expect(buildLaunchConfig({ ...BASE, fpvUptiltDeg: -5 }).camera.fpvUptiltDeg).toBe(0);
  });
});

describe('clampUptilt', () => {
  it('falls back to the default for a non-number', () => {
    expect(clampUptilt(Number.NaN)).toBe(DEFAULT_FPV_UPTILT_DEG);
    expect(clampUptilt(Number.POSITIVE_INFINITY)).toBe(DEFAULT_FPV_UPTILT_DEG);
  });
});

describe('parseLaunchConfig', () => {
  it('round-trips a config it wrote', () => {
    const config = buildLaunchConfig({ ...BASE, fpvUptiltDeg: 35 });
    const parsed = parseLaunchConfig(JSON.parse(serializeLaunchConfig(config)));
    expect(parsed.warnings).toEqual([]);
    expect(parsed.config).toEqual(config);
  });

  it('degrades on a partial config instead of failing', () => {
    const parsed = parseLaunchConfig({ schemaVersion: 1, region: { name: 'varel' } });
    expect(parsed.config).not.toBeNull();
    expect(parsed.config?.region.name).toBe('varel');
    expect(parsed.config?.camera.fpvUptiltDeg).toBe(DEFAULT_FPV_UPTILT_DEG);
    expect(parsed.warnings.join(' ')).toContain('region.home');
  });

  it('degrades on an empty object', () => {
    const parsed = parseLaunchConfig({});
    expect(parsed.config?.region.name).toBe('');
    expect(parsed.config?.camera.fpvUptiltDeg).toBe(DEFAULT_FPV_UPTILT_DEG);
  });

  it('reports a newer schema version rather than refusing it', () => {
    const parsed = parseLaunchConfig({ schemaVersion: 99, region: { name: 'bar', assetPath: '/x' } });
    expect(parsed.config?.region.name).toBe('bar');
    expect(parsed.warnings.join(' ')).toContain('newer than this build');
  });

  it('returns null only when the root is not an object', () => {
    expect(parseLaunchConfig('nope').config).toBeNull();
    expect(parseLaunchConfig(null).config).toBeNull();
    expect(parseLaunchConfig([1, 2]).config).toBeNull();
  });

  it('clamps a hand-edited uptilt and says so', () => {
    const parsed = parseLaunchConfig({ camera: { fpvUptiltDeg: 120 } });
    expect(parsed.config?.camera.fpvUptiltDeg).toBe(55);
    expect(parsed.warnings.join(' ')).toContain('clamped');
  });
});
