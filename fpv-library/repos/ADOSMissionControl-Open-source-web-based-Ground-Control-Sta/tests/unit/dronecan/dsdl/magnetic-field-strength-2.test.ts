/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  decodeMagneticFieldStrength2,
  encodeMagneticFieldStrength2,
} from "@/lib/dronecan/dsdl/magnetic-field-strength-2";

describe("dsdl MagneticFieldStrength2", () => {
  it("round-trips a typical 3-axis reading with no covariance", () => {
    const msg = {
      sensorId: 2,
      magneticFieldGa: [0.32, 0.05, 0.41] as [number, number, number],
      magneticFieldCovariance: [],
    };
    const buf = encodeMagneticFieldStrength2(msg);
    // 1 byte sensor_id + 3 * 2 bytes float16 = 7 bytes.
    expect(buf.length).toBe(7);
    const round = decodeMagneticFieldStrength2(buf);
    expect(round.sensorId).toBe(2);
    expect(round.magneticFieldGa[0]).toBeCloseTo(0.32, 2);
    expect(round.magneticFieldGa[1]).toBeCloseTo(0.05, 2);
    expect(round.magneticFieldGa[2]).toBeCloseTo(0.41, 2);
    expect(round.magneticFieldCovariance).toEqual([]);
  });

  it("preserves a covariance tail array of length 6", () => {
    const cov = [0.01, 0, 0, 0.01, 0, 0.02];
    const buf = encodeMagneticFieldStrength2({
      sensorId: 0,
      magneticFieldGa: [1, 2, 3],
      magneticFieldCovariance: cov,
    });
    // 1 + 6 + 6 * 2 = 19.
    expect(buf.length).toBe(1 + 3 * 2 + cov.length * 2);
    const round = decodeMagneticFieldStrength2(buf);
    expect(round.magneticFieldCovariance.length).toBe(cov.length);
    for (let i = 0; i < cov.length; i++) {
      expect(round.magneticFieldCovariance[i]).toBeCloseTo(cov[i], 2);
    }
  });

  it("decodes a hand-crafted wire payload with sensor_id=7 and known floats", () => {
    // sensor_id = 7, mag = [1.0, -1.0, 0.5], cov = [].
    // float16(1.0) = 0x3C00, float16(-1.0) = 0xBC00, float16(0.5) = 0x3800.
    // Bit stream is LSB-first, so each 16-bit word emits low byte then high.
    const buf = new Uint8Array([
      0x07, 0x00, 0x3c, 0x00, 0xbc, 0x00, 0x38,
    ]);
    const decoded = decodeMagneticFieldStrength2(buf);
    expect(decoded.sensorId).toBe(0x07);
    expect(decoded.magneticFieldGa[0]).toBe(1);
    expect(decoded.magneticFieldGa[1]).toBe(-1);
    expect(decoded.magneticFieldGa[2]).toBe(0.5);
  });
});
