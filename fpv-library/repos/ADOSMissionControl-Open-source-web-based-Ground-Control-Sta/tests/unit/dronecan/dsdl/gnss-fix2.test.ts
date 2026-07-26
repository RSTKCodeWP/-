/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  GNSS_TIME_STANDARD_UTC,
  MODE_SINGLE,
  STATUS_3D_FIX,
  decodeFix2,
  encodeFix2,
  type GnssFix2,
} from "@/lib/dronecan/dsdl/gnss-fix2";

function syntheticFix(): GnssFix2 {
  return {
    timestamp: { usecMonotonic: BigInt(1700000000000000) },
    gnssTimestamp: { usecMonotonic: BigInt(1700000000005000) },
    gnssTimeStandard: GNSS_TIME_STANDARD_UTC,
    numLeapSeconds: 18,
    latitudeDeg1e8: BigInt(3777490000),
    longitudeDeg1e8: BigInt(-12241940000),
    heightEllipsoidMm: 50_000,
    heightMslMm: 16_000,
    nedVelocity: [0.5, -0.25, 0.0],
    satsUsed: 12,
    status: STATUS_3D_FIX,
    mode: MODE_SINGLE,
    subMode: 0,
    covariance: [0.5, 0.0, 0.0, 0.5, 0.0, 1.0],
    pdop: 1.4,
  };
}

describe("dsdl gnss.Fix2", () => {
  it("round-trips a synthetic 3D fix with covariance and no ECEF block", () => {
    const original = syntheticFix();
    const buf = encodeFix2(original);
    // Sanity check: payload must straddle multiple frames.
    expect(buf.length).toBeGreaterThan(40);
    const decoded = decodeFix2(buf);
    expect(decoded.gnssTimeStandard).toBe(GNSS_TIME_STANDARD_UTC);
    expect(decoded.numLeapSeconds).toBe(18);
    expect(decoded.latitudeDeg1e8).toBe(BigInt(3777490000));
    expect(decoded.longitudeDeg1e8).toBe(BigInt(-12241940000));
    expect(decoded.heightEllipsoidMm).toBe(50_000);
    expect(decoded.heightMslMm).toBe(16_000);
    expect(decoded.satsUsed).toBe(12);
    expect(decoded.status).toBe(STATUS_3D_FIX);
    expect(decoded.mode).toBe(MODE_SINGLE);
    expect(decoded.subMode).toBe(0);
    expect(decoded.covariance.length).toBe(6);
    expect(decoded.covariance[5]).toBeCloseTo(1.0, 2);
    expect(decoded.pdop).toBeCloseTo(1.4, 2);
    expect(decoded.timestamp.usecMonotonic).toBe(BigInt(1700000000000000));
    expect(decoded.ecefPositionVelocity).toBeUndefined();
  });

  it("preserves negative int37 latitude / longitude round-trip", () => {
    const fix = syntheticFix();
    fix.latitudeDeg1e8 = -(BigInt(1) << BigInt(36));
    fix.longitudeDeg1e8 = (BigInt(1) << BigInt(36)) - BigInt(1);
    const decoded = decodeFix2(encodeFix2(fix));
    expect(decoded.latitudeDeg1e8).toBe(-(BigInt(1) << BigInt(36)));
    expect(decoded.longitudeDeg1e8).toBe((BigInt(1) << BigInt(36)) - BigInt(1));
  });

  it("preserves negative int27 heights round-trip", () => {
    const fix = syntheticFix();
    fix.heightEllipsoidMm = -(1 << 26);
    fix.heightMslMm = (1 << 26) - 1;
    const decoded = decodeFix2(encodeFix2(fix));
    expect(decoded.heightEllipsoidMm).toBe(-(1 << 26));
    expect(decoded.heightMslMm).toBe((1 << 26) - 1);
  });

  // Frozen wire-byte fixture for the synthetic 3D fix above. Locked in
  // by encoding once and recording the resulting buffer verbatim. A
  // symmetric bug across encode+decode (the class of bug that landed
  // and was reverted on `ned_velocity` when float16 was mistakenly used
  // in both halves) leaves the round-trip green but flips these bytes.
  // Touch the fixture only when the wire layout itself changes, and
  // when you do, document the wire-spec change in the same commit.
  const FIX2_FIXTURE_HEX =
    "00401e18240a0688531e18240a06020012e0d152261d8afd241c400d0300d007000000003f000080be00000000cc001800380000000000380000003c9a3d";

  function hexToBytes(hex: string): Uint8Array {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) {
      out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    }
    return out;
  }

  it("encodes the synthetic 3D fix to the frozen wire-byte fixture", () => {
    const buf = encodeFix2(syntheticFix());
    const hex = Array.from(buf)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    expect(hex).toBe(FIX2_FIXTURE_HEX);
  });

  it("decodes the frozen wire-byte fixture to the expected field values", () => {
    // Pure decode path — no encode in the test. A symmetric encode+decode
    // regression that leaves round-trips passing will still flip these
    // assertions because we are comparing decoded fields against
    // hand-chosen ground-truth scalars rather than re-encoded output.
    const decoded = decodeFix2(hexToBytes(FIX2_FIXTURE_HEX));
    expect(decoded.gnssTimeStandard).toBe(GNSS_TIME_STANDARD_UTC);
    expect(decoded.numLeapSeconds).toBe(18);
    expect(decoded.latitudeDeg1e8).toBe(BigInt(3777490000));
    expect(decoded.longitudeDeg1e8).toBe(BigInt(-12241940000));
    expect(decoded.heightEllipsoidMm).toBe(50_000);
    expect(decoded.heightMslMm).toBe(16_000);
    expect(decoded.satsUsed).toBe(12);
    expect(decoded.status).toBe(STATUS_3D_FIX);
    expect(decoded.mode).toBe(MODE_SINGLE);
    expect(decoded.subMode).toBe(0);
    // ned_velocity round-tripped through float32 in the fixture; assert
    // exact bit equality rather than approximate to catch a float16
    // regression (the exact bug class the fixture is here to guard).
    expect(decoded.nedVelocity[0]).toBe(0.5);
    expect(decoded.nedVelocity[1]).toBe(-0.25);
    expect(decoded.nedVelocity[2]).toBe(0);
    expect(decoded.timestamp.usecMonotonic).toBe(BigInt(1700000000000000));
    expect(decoded.gnssTimestamp.usecMonotonic).toBe(BigInt(1700000000005000));
    expect(decoded.ecefPositionVelocity).toBeUndefined();
  });

  it("round-trips an ECEFPositionVelocity tail block", () => {
    const fix = syntheticFix();
    fix.ecefPositionVelocity = {
      velocityXyz: [1.0, -2.0, 3.0],
      positionXyzMm: [
        BigInt(123456789),
        BigInt(-987654321),
        BigInt(50_000_000),
      ],
      covariance: [0.1, 0.2, 0.3],
    };
    const decoded = decodeFix2(encodeFix2(fix));
    expect(decoded.ecefPositionVelocity).toBeDefined();
    const ecef = decoded.ecefPositionVelocity!;
    expect(ecef.velocityXyz[0]).toBeCloseTo(1.0, 2);
    expect(ecef.velocityXyz[2]).toBeCloseTo(3.0, 2);
    expect(ecef.positionXyzMm[0]).toBe(BigInt(123456789));
    expect(ecef.positionXyzMm[1]).toBe(BigInt(-987654321));
    expect(ecef.covariance.length).toBe(3);
    expect(ecef.covariance[1]).toBeCloseTo(0.2, 2);
  });
});
