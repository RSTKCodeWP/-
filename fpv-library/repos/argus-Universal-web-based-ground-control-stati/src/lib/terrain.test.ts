import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// backend.ts accesses `window` at module scope — stub before import
vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });

const { interpolateRoute, getElevation, getElevationProfile, adjustWaypointsForTerrain } = await import('./terrain');

describe('interpolateRoute', () => {
  it('returns single point for a single waypoint', () => {
    const result = interpolateRoute([{ lat: 34.258, lon: 108.942 }]);
    expect(result.length).toBe(1);
    expect(result[0].wpIndex).toBe(0);
    expect(result[0].lat).toBe(34.258);
    expect(result[0].lon).toBe(108.942);
  });

  it('returns empty array for empty input', () => {
    expect(interpolateRoute([])).toEqual([]);
  });

  it('creates intermediate points between two waypoints', () => {
    // Two waypoints ~1.1 km apart (0.01 deg lat at 34 N ~ 1113m)
    const wps = [
      { lat: 34.258, lon: 108.942 },
      { lat: 34.268, lon: 108.942 },
    ];
    const result = interpolateRoute(wps, 50);
    // ~1113m / 50m step = ~23 steps, plus the final waypoint
    expect(result.length).toBeGreaterThan(10);
    // First point matches first waypoint
    expect(result[0].lat).toBe(wps[0].lat);
    expect(result[0].lon).toBe(wps[0].lon);
    expect(result[0].wpIndex).toBe(0);
    // Last point matches last waypoint
    const last = result[result.length - 1];
    expect(last.lat).toBe(wps[1].lat);
    expect(last.lon).toBe(wps[1].lon);
    expect(last.wpIndex).toBe(1);
  });

  it('intermediate points have wpIndex -1', () => {
    const wps = [
      { lat: 34.258, lon: 108.942 },
      { lat: 34.268, lon: 108.942 },
    ];
    const result = interpolateRoute(wps, 50);
    const intermediates = result.filter((p) => p.wpIndex === -1);
    expect(intermediates.length).toBeGreaterThan(0);
  });

  it('larger step size produces fewer points', () => {
    const wps = [
      { lat: 34.258, lon: 108.942 },
      { lat: 34.268, lon: 108.942 },
    ];
    const fine = interpolateRoute(wps, 25);
    const coarse = interpolateRoute(wps, 200);
    expect(fine.length).toBeGreaterThan(coarse.length);
  });

  it('handles three-waypoint route correctly', () => {
    const wps = [
      { lat: 34.258, lon: 108.942 },
      { lat: 34.26, lon: 108.942 },
      { lat: 34.26, lon: 108.944 },
    ];
    const result = interpolateRoute(wps, 100);
    // Should have waypoint indices 0, 1, 2 somewhere in the result
    const wpIndices = result.filter((p) => p.wpIndex >= 0).map((p) => p.wpIndex);
    expect(wpIndices).toContain(0);
    expect(wpIndices).toContain(1);
    expect(wpIndices).toContain(2);
  });
});

describe('getElevation', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    // Re-stub window for subsequent tests
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });
  });

  it('fetches elevation from API on cache miss', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [456.7] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const elev = await getElevation(35.1234, 109.5678);
    expect(elev).toBe(456.7);
    expect(fetch).toHaveBeenCalledTimes(1);
    const callUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(callUrl).toContain('/api/terrain/elevation');
    expect(callUrl).toContain('35.123400');
    expect(callUrl).toContain('109.567800');
  });

  it('returns cached value on cache hit (no fetch)', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [100.0] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    // First call — cache miss
    const elev1 = await getElevation(40.0001, 116.0001);
    expect(fetch).toHaveBeenCalledTimes(1);

    // Second call with same coords (rounded to 4dp) — cache hit
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockClear();
    const elev2 = await getElevation(40.00014, 116.00014);
    expect(fetch).not.toHaveBeenCalled();
    expect(elev2).toBe(elev1);
  });

  it('throws on non-OK response', async () => {
    const mockResponse = {
      ok: false,
      status: 500,
      json: () => Promise.resolve({}),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    await expect(getElevation(0, 0)).rejects.toThrow('Terrain API 500');
  });
});

describe('getElevationProfile', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });
  });

  it('returns empty array for empty input', async () => {
    const result = await getElevationProfile([]);
    expect(result).toEqual([]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('returns cached values when all points are cached', async () => {
    // First seed the cache by fetching single points
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [200.0] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    // Seed cache for a specific point
    await getElevation(50.1111, 10.2222);
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockClear();

    // Now getElevationProfile for that same point (rounded to 4dp match)
    const result = await getElevationProfile([{ lat: 50.1111, lon: 10.2222 }]);
    expect(result).toEqual([200.0]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('fetches from API when not all points are cached', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [300.0, 310.0, 320.0] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const points = [
      { lat: 60.0001, lon: 20.0001 },
      { lat: 60.0002, lon: 20.0002 },
      { lat: 60.0003, lon: 20.0003 },
    ];
    const result = await getElevationProfile(points);
    expect(result).toEqual([300.0, 310.0, 320.0]);
    expect(fetch).toHaveBeenCalledTimes(1);

    // Verify the URL contains semicolon-separated points
    const callUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(callUrl).toContain(';');
    expect(callUrl).toContain('60.000100');
    expect(callUrl).toContain('20.000100');
  });

  it('populates cache after fetch', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [400.0, 410.0] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const points = [
      { lat: 70.1234, lon: 30.5678 },
      { lat: 70.2345, lon: 30.6789 },
    ];
    await getElevationProfile(points);
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockClear();

    // Second call should use cache
    const result = await getElevationProfile(points);
    expect(result).toEqual([400.0, 410.0]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('throws on non-OK response', async () => {
    const mockResponse = { ok: false, status: 404 };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const points = [{ lat: 80.0, lon: 40.0 }];
    await expect(getElevationProfile(points)).rejects.toThrow('Terrain API 404');
  });
});

describe('adjustWaypointsForTerrain', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } });
  });

  it('adjusts waypoint altitudes relative to home elevation', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [100, 150, 200] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const wps = [
      { lat: 90.0001, lon: 50.0001, alt: 50 },
      { lat: 90.0002, lon: 50.0002, alt: 50 },
      { lat: 90.0003, lon: 50.0003, alt: 50 },
    ];
    const result = await adjustWaypointsForTerrain(wps, 30);

    // No homeLatLon → uses elevations[0]=100 as home reference.
    // alt = (groundElev - homeElev) + targetAGL (frame=3 relative to home)
    expect(result[0].alt).toBe(30); // (100-100) + 30
    expect(result[1].alt).toBe(80); // (150-100) + 30
    expect(result[2].alt).toBe(130); // (200-100) + 30
  });

  it('does not mutate original waypoints', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [500] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const wps = [{ lat: 91.0001, lon: 51.0001, alt: 10 }];
    const result = await adjustWaypointsForTerrain(wps, 50);

    expect(wps[0].alt).toBe(10); // Original unchanged
    expect(result[0].alt).toBe(50); // (500-500) + 50 = 50 (home = first WP ground)
  });

  it('preserves lat/lon in returned waypoints', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [250] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const wps = [{ lat: 92.1234, lon: 52.5678, alt: 99 }];
    const result = await adjustWaypointsForTerrain(wps, 20);

    expect(result[0].lat).toBe(92.1234);
    expect(result[0].lon).toBe(52.5678);
    expect(result[0].alt).toBe(20); // (250-250) + 20 (single WP, home = itself)
  });

  it('rounds altitude to nearest integer', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [123.7] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const wps = [{ lat: 93.0001, lon: 53.0001, alt: 0 }];
    const result = await adjustWaypointsForTerrain(wps, 10.3);

    // (123.7-123.7) + 10.3 = 10.3 → Math.round = 10
    expect(result[0].alt).toBe(10);
  });

  it('uses explicit home position for MSL-to-relative conversion', async () => {
    let callCount = 0;
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // First call: batch profile for waypoints
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ elevations: [200, 300] }) });
      }
      // Second call: home elevation query
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ elevations: [50] }) });
    });

    const wps = [
      { lat: 94.0001, lon: 54.0001, alt: 0 },
      { lat: 94.0002, lon: 54.0002, alt: 0 },
    ];
    const home = { lat: 94.001, lon: 54.001 };
    const result = await adjustWaypointsForTerrain(wps, 30, home);

    // homeElev=50 (from separate query). alt = (groundElev - 50) + 30
    expect(result[0].alt).toBe(180); // (200-50) + 30
    expect(result[1].alt).toBe(280); // (300-50) + 30
  });

  it('handles empty waypoints array', async () => {
    const mockResponse = {
      ok: true,
      json: () => Promise.resolve({ elevations: [] }),
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

    const result = await adjustWaypointsForTerrain([], 50);
    expect(result).toEqual([]);
  });
});
