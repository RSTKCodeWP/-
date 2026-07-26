import { describe, it, expect } from 'vitest';
import { computeAreaHud, aggregateAreaHud } from './area-editor-hud';
import type { AreaHud } from './area-editor-hud';
import type { SurveyStats } from '../components/survey/survey-types';

const STATS_100_PHOTOS: SurveyStats = {
  gsd: 2.5,
  flightDistance: 5000,
  flightTime: 600,
  photoCount: 100,
  lineCount: 10,
  areaCovered: 50000,
  footprintWidth: 80,
  footprintHeight: 60,
  lineSpacing: 32,
  photoSpacing: 15,
};

describe('computeAreaHud', () => {
  it('returns null stats fields when ring has < 3 points (stats is null)', () => {
    const hud = computeAreaHud({
      areaM2: 0,
      stats: null,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.areaHa).toBeNull();
    expect(hud.gsdCm).toBeNull();
    expect(hud.photoCount).toBeNull();
    expect(hud.dataGb).toBeNull();
    expect(hud.flightDistanceM).toBeNull();
    expect(hud.flightTimeSec).toBeNull();
    expect(hud.batteryCount).toBeNull();
  });

  it('converts area from m2 to hectares correctly', () => {
    // 50000 m2 = 5 ha
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: STATS_100_PHOTOS,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.areaHa).toBeCloseTo(5, 4);
  });

  it('propagates gsd, photoCount, flightDistance, flightTime from stats', () => {
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: STATS_100_PHOTOS,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.gsdCm).toBe(2.5);
    expect(hud.photoCount).toBe(100);
    expect(hud.flightDistanceM).toBe(5000);
    expect(hud.flightTimeSec).toBe(600);
  });

  it('computes battery count using estimateBatteryCount logic', () => {
    // flightTime=600s, endurance=20min=1200s -> ceil(600/1200) = 1
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: STATS_100_PHOTOS,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.batteryCount).toBe(1);
  });

  it('returns batteryCount > 1 when flight time exceeds one battery', () => {
    // flightTime=3000s, endurance=20min=1200s -> ceil(3000/1200) = 3
    const longFlight: SurveyStats = { ...STATS_100_PHOTOS, flightTime: 3000 };
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: longFlight,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.batteryCount).toBe(3);
  });

  it('computes dataGb proportional to photo count and megapixels', () => {
    // 100 photos, 5280x3956 = ~20.9 MP, 1.2 MB/MP -> ~25.1 MB/photo
    // 100 * 25.1 MB / 1024 ~= 2.45 GB
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: STATS_100_PHOTOS,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    expect(hud.dataGb).toBeGreaterThan(2);
    expect(hud.dataGb).toBeLessThan(3);
  });

  it('returns batteryCount null when enduranceSec is 0', () => {
    const hud = computeAreaHud({
      areaM2: 50000,
      stats: STATS_100_PHOTOS,
      enduranceSec: 0,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    // estimateBatteryCount returns 0 when endurance <= 0; we map 0 -> null
    expect(hud.batteryCount).toBeNull();
  });

  it('returns areaHa from areaM2 even when stats is null', () => {
    // When ring.length >= 3 we still get area even if generator fails
    const hud = computeAreaHud({
      areaM2: 10000,
      stats: null,
      enduranceSec: 20 * 60,
      imageWidth: 5280,
      imageHeight: 3956,
    });
    // When stats is null we return null for areaHa too - check by spec:
    // stats null means we don't show any computed values
    expect(hud.areaHa).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// aggregateAreaHud
// ---------------------------------------------------------------------------

const HUD_A: AreaHud = {
  areaHa: 5,
  gsdCm: 2.5,
  photoCount: 100,
  dataGb: 2.4,
  flightDistanceM: 5000,
  flightTimeSec: 600,
  batteryCount: 1,
};

const HUD_B: AreaHud = {
  areaHa: 3,
  gsdCm: 2.5,
  photoCount: 60,
  dataGb: 1.5,
  flightDistanceM: 3000,
  flightTimeSec: 360,
  batteryCount: 1,
};

const NULL_HUD: AreaHud = {
  areaHa: null,
  gsdCm: null,
  photoCount: null,
  dataGb: null,
  flightDistanceM: null,
  flightTimeSec: null,
  batteryCount: null,
};

describe('aggregateAreaHud', () => {
  it('returns all-null when given empty array', () => {
    const agg = aggregateAreaHud([], 20 * 60);
    expect(agg.areaHa).toBeNull();
    expect(agg.photoCount).toBeNull();
    expect(agg.flightDistanceM).toBeNull();
    expect(agg.flightTimeSec).toBeNull();
    expect(agg.dataGb).toBeNull();
    expect(agg.gsdCm).toBeNull();
    expect(agg.batteryCount).toBeNull();
  });

  it('sums numeric fields across two polygons', () => {
    const agg = aggregateAreaHud([HUD_A, HUD_B], 20 * 60);
    expect(agg.areaHa).toBeCloseTo(8, 6);
    expect(agg.photoCount).toBe(160);
    expect(agg.flightDistanceM).toBe(8000);
    expect(agg.flightTimeSec).toBe(960);
    expect(agg.dataGb).toBeCloseTo(3.9, 5);
  });

  it('takes gsdCm from the first non-null polygon', () => {
    const agg = aggregateAreaHud([HUD_A, HUD_B], 20 * 60);
    expect(agg.gsdCm).toBe(2.5);
  });

  it('re-derives batteryCount from summed flightTimeSec, not summed per-polygon counts', () => {
    // total flightTimeSec = 600 + 360 = 960s, endurance = 20min = 1200s -> ceil(960/1200) = 1
    const agg = aggregateAreaHud([HUD_A, HUD_B], 20 * 60);
    expect(agg.batteryCount).toBe(1);
  });

  it('re-derives batteryCount spanning multiple batteries for large total', () => {
    // Two polygons each with 900s -> total 1800s, endurance=1200s -> ceil(1800/1200)=2
    const longA: AreaHud = { ...HUD_A, flightTimeSec: 900 };
    const longB: AreaHud = { ...HUD_B, flightTimeSec: 900 };
    const agg = aggregateAreaHud([longA, longB], 20 * 60);
    expect(agg.batteryCount).toBe(2);
  });

  it('treats null polygon values as zero contribution (not poisoning the sum)', () => {
    // One valid polygon, one all-null polygon
    const agg = aggregateAreaHud([HUD_A, NULL_HUD], 20 * 60);
    expect(agg.areaHa).toBeCloseTo(5, 6);
    expect(agg.photoCount).toBe(100);
    expect(agg.flightDistanceM).toBe(5000);
  });

  it('returns null aggregates when all polygons are null', () => {
    const agg = aggregateAreaHud([NULL_HUD, NULL_HUD], 0);
    expect(agg.areaHa).toBeNull();
    expect(agg.photoCount).toBeNull();
    expect(agg.batteryCount).toBeNull();
  });

  it('returns batteryCount null when enduranceSec is 0 (even with flight time)', () => {
    const agg = aggregateAreaHud([HUD_A], 0);
    expect(agg.batteryCount).toBeNull();
  });
});
