/**
 * Verification harness for the bundled parameter-metadata snapshots.
 *
 * Proves the committed floor is complete + correct without a network fetch:
 *   - minimum param count per firmware (no silently-truncated snapshot),
 *   - every enum/bitmask param carries a non-empty label table (no guessed or
 *     empty labels — the "miss nothing" gate),
 *   - golden popular params decode to the exact known labels,
 *   - the float-enum-code regression (0.1 "Very Low") stays intact.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { deserializeMetaMap } from "@/lib/protocol/param-metadata/types";
import type { ParamSnapshot } from "@/lib/protocol/param-metadata";

const DIR = resolve(process.cwd(), "public", "param-metadata");

function load(file: string) {
  const buf = readFileSync(resolve(DIR, file));
  const snap = JSON.parse(gunzipSync(buf).toString("utf8")) as ParamSnapshot;
  return { snap, map: deserializeMetaMap(snap.params) };
}

const FIRMWARES = [
  { file: "ardupilot-copter.json.gz", min: 800 },
  { file: "ardupilot-plane.json.gz", min: 800 },
  { file: "ardupilot-rover.json.gz", min: 600 },
  { file: "ardupilot-sub.json.gz", min: 600 },
  { file: "px4.json.gz", min: 1000 },
  { file: "inav.json.gz", min: 600 },
  { file: "betaflight.json.gz", min: 2 },
];

describe("bundled parameter snapshots — structural integrity", () => {
  for (const { file, min } of FIRMWARES) {
    describe(file, () => {
      const { snap, map } = load(file);

      it(`has at least ${min} params and a matching provenance count`, () => {
        expect(map.size).toBeGreaterThanOrEqual(min);
        expect(snap.provenance.paramCount).toBe(snap.params.length);
      });

      it("every param has a name", () => {
        for (const m of map.values()) expect(m.name.length).toBeGreaterThan(0);
      });

      it("every enum/bitmask param has a non-empty label table (no guessed/empty labels)", () => {
        for (const m of map.values()) {
          if (m.values) {
            expect(m.values.size).toBeGreaterThan(0);
            for (const label of m.values.values()) expect(label.length).toBeGreaterThan(0);
          }
          if (m.bitmask) {
            expect(m.bitmask.size).toBeGreaterThan(0);
            for (const label of m.bitmask.values()) expect(label.length).toBeGreaterThan(0);
          }
        }
      });
    });
  }
});

describe("bundled parameter snapshots — golden labels", () => {
  it("ArduCopter INS_HNTCH_OPTS bitmask is exact", () => {
    const { map } = load("ardupilot-copter.json.gz");
    const m = map.get("INS_HNTCH_OPTS");
    expect(m?.bitmask?.get(0)).toBe("Double notch");
    expect(m?.bitmask?.get(2)).toBe("Update at loop rate");
    expect(m?.bitmask?.get(3)).toBe("EnableOnAllIMUs");
  });

  it("ArduCopter FENCE_TYPE bitmask is present", () => {
    const { map } = load("ardupilot-copter.json.gz");
    expect(map.get("FENCE_TYPE")?.bitmask?.get(0)).toBe("Max altitude");
  });

  it("ArduCopter ACRO_RP_EXPO preserves non-integer enum codes (0.1)", () => {
    const { map } = load("ardupilot-copter.json.gz");
    const m = map.get("ACRO_RP_EXPO");
    expect(m?.values?.get(0.1)).toBe("Very Low");
    expect(m?.values?.get(0.2)).toBe("Low");
  });

  it("ArduCopter FLTMODE1 enum maps 5 to Loiter", () => {
    const { map } = load("ardupilot-copter.json.gz");
    expect(map.get("FLTMODE1")?.values?.get(5)).toBe("Loiter");
  });

  it("PX4 COM_RC_OVERRIDE bitmask is present", () => {
    const { map } = load("px4.json.gz");
    expect(map.get("COM_RC_OVERRIDE")?.bitmask?.size).toBeGreaterThanOrEqual(2);
  });

  it("PX4 COM_FLTMODE1 enum includes the negative Unassigned code", () => {
    const { map } = load("px4.json.gz");
    expect(map.get("COM_FLTMODE1")?.values?.get(-1)).toBe("Unassigned");
  });

  it("iNav full named-settings registry + curated virtual-param entries", () => {
    const { map } = load("inav.json.gz");
    // Full named settings (lowercase) from settings.yaml.
    expect(map.size).toBeGreaterThan(600);
    expect(map.get("motor_pwm_protocol")?.values?.get(0)).toBe("STANDARD");
    expect(map.get("motor_pwm_protocol")?.values?.get(1)).toBe("ONESHOT125");
    // Curated virtual-param entries (uppercase) for the fallback path.
    expect(map.get("FEATURE_FLAGS")?.bitmask?.size).toBeGreaterThan(0);
    expect(map.get("FAILSAFE_PROCEDURE")?.values?.get(0)).toBe("LAND");
    expect(map.get("DISARM_KILL_SWITCH")?.values?.get(1)).toBe("ON");
  });

  it("Betaflight FEATURE_FLAGS is a non-empty bitmask", () => {
    const { map } = load("betaflight.json.gz");
    expect(map.get("FEATURE_FLAGS")?.bitmask?.size).toBeGreaterThan(0);
    expect(map.get("FEATURE_FLAGS")?.bitmask?.get(0)).toBe("RX_PPM");
  });
});
