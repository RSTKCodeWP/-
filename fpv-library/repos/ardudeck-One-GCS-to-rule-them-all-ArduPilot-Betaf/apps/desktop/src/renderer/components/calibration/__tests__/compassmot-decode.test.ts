import { describe, it, expect } from 'vitest';
import { decodeCompassMot, interferenceQuality } from '../CompassMotDialog';

/**
 * Serialize a COMPASSMOT_STATUS (msgid 177) payload in MAVLink wire order
 * (fields sorted by size descending, stable): the four floats
 * current/CompensationX/Y/Z, then the two uint16s throttle/interference.
 * Matches Mission Planner's mavlink_compassmot_status_t packet constructor.
 */
function encode(fields: {
  current: number;
  compX: number;
  compY: number;
  compZ: number;
  throttleDeciPct: number;
  interference: number;
}): number[] {
  const bytes = new Uint8Array(20);
  const view = new DataView(bytes.buffer);
  view.setFloat32(0, fields.current, true);
  view.setFloat32(4, fields.compX, true);
  view.setFloat32(8, fields.compY, true);
  view.setFloat32(12, fields.compZ, true);
  view.setUint16(16, fields.throttleDeciPct, true);
  view.setUint16(18, fields.interference, true);
  return Array.from(bytes);
}

describe('decodeCompassMot', () => {
  it('decodes fields at the correct wire offsets', () => {
    const payload = encode({
      current: 12.5,
      compX: 0.11,
      compY: -0.22,
      compZ: 0.33,
      throttleDeciPct: 555, // 55.5%
      interference: 42,
    });
    const s = decodeCompassMot(payload)!;
    expect(s.current).toBeCloseTo(12.5, 3);
    expect(s.compX).toBeCloseTo(0.11, 3);
    expect(s.compY).toBeCloseTo(-0.22, 3);
    expect(s.compZ).toBeCloseTo(0.33, 3);
    expect(s.throttle).toBeCloseTo(55.5, 3);
    expect(s.interference).toBe(42);
  });

  it('pads a zero-trimmed MAVLink v2 payload', () => {
    // Trailing zero fields dropped by v2 truncation: only current is non-zero.
    const full = encode({ current: 3.0, compX: 0, compY: 0, compZ: 0, throttleDeciPct: 0, interference: 0 });
    const trimmed = full.slice(0, 4); // just the current float
    const s = decodeCompassMot(trimmed)!;
    expect(s.current).toBeCloseTo(3.0, 3);
    expect(s.throttle).toBe(0);
    expect(s.interference).toBe(0);
  });
});

describe('interferenceQuality', () => {
  it('bands interference per ArduPilot guidance', () => {
    expect(interferenceQuality(10).tone).toBe('good');
    expect(interferenceQuality(29).tone).toBe('good');
    expect(interferenceQuality(30).tone).toBe('marginal');
    expect(interferenceQuality(59).tone).toBe('marginal');
    expect(interferenceQuality(60).tone).toBe('bad');
    expect(interferenceQuality(85).tone).toBe('bad');
  });
});
