import { describe, it, expect } from 'vitest';
import { generateCrosshatch } from './crosshatch-generator';
import { surveyToMissionItems } from '../mission-builder';
import { DEFAULT_SURVEY_CONFIG, type SurveyConfig, type LatLng } from '../survey-types';
import { MAV_CMD } from '../../../../shared/mission-types';

const SQUARE: LatLng[] = [
  { lat: 0, lng: 0 },
  { lat: 0, lng: 0.003 },
  { lat: 0.003, lng: 0.003 },
  { lat: 0.003, lng: 0 },
];

function config(overrides: Partial<SurveyConfig> = {}): SurveyConfig {
  return { ...DEFAULT_SURVEY_CONFIG, polygon: SQUARE, pattern: 'crosshatch', altitude: 80, ...overrides };
}

describe('generateCrosshatch second-pass altitude offset', () => {
  it('omits per-waypoint altitudes when offset is 0', () => {
    const r = generateCrosshatch(config({ crossGridAltitudeOffset: 0 }));
    expect(r.altitudes).toBeUndefined();
  });

  it('carries two altitudes when offset is set, second pass higher', () => {
    const r = generateCrosshatch(config({ crossGridAltitudeOffset: 50 }));
    expect(r.altitudes).toBeDefined();
    const alts = new Set(r.altitudes);
    expect(alts.has(80)).toBe(true);
    expect(alts.has(120)).toBe(true); // 80 * 1.5
    expect(r.altitudes!.length).toBe(r.waypoints.length);
  });

  it('mission builder emits the per-pass altitude on the NAV_WAYPOINTs', () => {
    const cfg = config({ crossGridAltitudeOffset: 25 });
    const r = generateCrosshatch(cfg);
    const items = surveyToMissionItems(r, cfg);
    const wpAlts = new Set(
      items.filter((it) => it.command === MAV_CMD.NAV_WAYPOINT).map((it) => Math.round(it.altitude)),
    );
    expect(wpAlts.has(80)).toBe(true);
    expect(wpAlts.has(100)).toBe(true); // 80 * 1.25
  });
});
