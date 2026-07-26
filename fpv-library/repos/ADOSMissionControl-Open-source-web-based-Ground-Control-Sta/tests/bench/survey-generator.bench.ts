import { describe, bench } from 'vitest';
import { generateSurvey } from '@/lib/patterns/survey-generator';
import type { SurveyConfig } from '@/lib/patterns/types';

// Realistic survey polygon: ~1 km^2 area in Bangalore
const smallPolygon: [number, number][] = [
  [12.9700, 77.5900],
  [12.9700, 77.6000],
  [12.9800, 77.6000],
  [12.9800, 77.5900],
];

// Larger polygon: ~4 km^2 irregular area
const largePolygon: [number, number][] = [
  [12.9600, 77.5800],
  [12.9600, 77.6100],
  [12.9750, 77.6200],
  [12.9900, 77.6100],
  [12.9900, 77.5800],
  [12.9800, 77.5700],
];

const baseConfig: SurveyConfig = {
  polygon: smallPolygon,
  gridAngle: 0,
  lineSpacing: 50,
  turnAroundDistance: 20,
  entryLocation: 'topLeft',
  flyAlternateTransects: false,
  cameraTriggerDistance: 10,
  altitude: 80,
  speed: 8,
};

describe('Survey Generator Benchmarks', () => {
  bench('small polygon, 50m spacing', () => {
    generateSurvey({ ...baseConfig, polygon: smallPolygon, lineSpacing: 50 });
  });

  bench('small polygon, 10m spacing (dense)', () => {
    generateSurvey({ ...baseConfig, polygon: smallPolygon, lineSpacing: 10 });
  });

  bench('large polygon, 50m spacing', () => {
    generateSurvey({ ...baseConfig, polygon: largePolygon, lineSpacing: 50 });
  });

  bench('large polygon, 10m spacing (dense)', () => {
    generateSurvey({ ...baseConfig, polygon: largePolygon, lineSpacing: 10 });
  });

  bench('crosshatch pattern', () => {
    generateSurvey({ ...baseConfig, polygon: smallPolygon, crosshatch: true });
  });

  bench('45-degree grid angle', () => {
    generateSurvey({ ...baseConfig, polygon: smallPolygon, gridAngle: 45 });
  });

  bench('alternate transects', () => {
    generateSurvey({ ...baseConfig, polygon: smallPolygon, flyAlternateTransects: true });
  });
});
