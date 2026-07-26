import { describe, it, expect } from 'vitest';
import { formatDistance, formatArea, formatSpeed, formatAltitude } from '@/lib/units/format';
import { parseLatLon } from '@/lib/geocoding/parse-latlon';

describe('units/format', () => {
  it('formats distance metric vs imperial', () => {
    expect(formatDistance(500, 'metric')).toBe('500 m');
    expect(formatDistance(2500, 'metric')).toBe('2.50 km');
    expect(formatDistance(500, 'imperial')).toBe('1640 ft');
    expect(formatDistance(2000, 'imperial')).toBe('1.24 mi');
    expect(formatDistance(NaN)).toBe('—');
  });
  it('formats speed + altitude imperial', () => {
    expect(formatSpeed(10, 'metric')).toBe('10.0 m/s');
    expect(formatSpeed(10, 'imperial')).toBe('22.4 mph');
    expect(formatAltitude(100, 'imperial')).toBe('328 ft');
  });
  it('formats area', () => {
    expect(formatArea(500, 'metric')).toBe('500 m²');
    expect(formatArea(50000, 'metric')).toBe('5.00 ha');
    expect(formatArea(5000, 'imperial')).toBe('1.24 ac');
  });
});

describe('parseLatLon', () => {
  it('parses decimal + comma', () => {
    expect(parseLatLon('12.97, 77.59')).toEqual({ lat: 12.97, lon: 77.59 });
  });
  it('parses whitespace-separated', () => {
    expect(parseLatLon('12.97 77.59')).toEqual({ lat: 12.97, lon: 77.59 });
  });
  it('parses hemisphere suffixes and reorders when lon-first', () => {
    expect(parseLatLon('12.97N 77.59E')).toEqual({ lat: 12.97, lon: 77.59 });
    expect(parseLatLon('77.59E, 12.97N')).toEqual({ lat: 12.97, lon: 77.59 });
    expect(parseLatLon('33.86S 151.21E')).toEqual({ lat: -33.86, lon: 151.21 });
  });
  it('rejects out-of-range + non-coordinates', () => {
    expect(parseLatLon('Bangalore')).toBeNull();
    expect(parseLatLon('91, 0')).toBeNull();
    expect(parseLatLon('12.97')).toBeNull();
  });
});
