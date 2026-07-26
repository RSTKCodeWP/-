/**
 * @module protocol/component-metadata.test
 * @description Unit tests for the MAVLink COMPONENT_METADATA (msg 397)
 * decoder, its independently-derived CRC_EXTRA seed, and the parameter
 * metadata provider's overlay-precedence merge (a live, FC-served entry wins
 * over a bundled-floor entry for the same parameter).
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeComponentMetadata } from "../messages/vehicle-info";
import { crc16Accumulate, CRC_EXTRA, PAYLOAD_LENGTHS } from "../mavlink-parser";
import { mergeMetaMaps } from "../param-metadata/merge";
import type { ParamMetadata } from "../param-metadata/types";

describe("COMPONENT_METADATA CRC_EXTRA + payload length", () => {
  it("derives CRC_EXTRA = 182 from the message signature (independent of the table)", () => {
    // MAVLink CRC_EXTRA: X.25 CRC over "NAME " then, per field in WIRE order
    // (fields sorted descending by base-type size; ties keep declared order),
    // "type " "name ", plus the array-length byte for array fields, folded to
    // 8 bits. COMPONENT_METADATA has no <extensions/> block, and its three
    // fields (uint32, uint32, char[100]) are already in wire order.
    const accStr = (s: string, crc: number) => {
      for (let i = 0; i < s.length; i++) crc = crc16Accumulate(s.charCodeAt(i), crc);
      return crc;
    };
    let crc = 0xffff;
    crc = accStr("COMPONENT_METADATA ", crc);
    crc = accStr("uint32_t time_boot_ms ", crc);
    crc = accStr("uint32_t file_crc ", crc);
    crc = accStr("char uri ", crc);
    crc = crc16Accumulate(100, crc); // uri is char[100]
    const extra = (crc ^ (crc >> 8)) & 0xff;
    expect(extra).toBe(182);
    expect(CRC_EXTRA.get(397)).toBe(182);
  });

  it("registers the canonical payload length (108 bytes)", () => {
    expect(PAYLOAD_LENGTHS.get(397)).toBe(108);
  });
});

describe("decodeComponentMetadata", () => {
  function buildPayload(timeBootMs: number, fileCrc: number, uri: string): DataView {
    const buf = new Uint8Array(108);
    const dv = new DataView(buf.buffer);
    dv.setUint32(0, timeBootMs, true);
    dv.setUint32(4, fileCrc, true);
    const uriBytes = new TextEncoder().encode(uri);
    buf.set(uriBytes.subarray(0, 100), 8);
    // Remaining uri bytes stay zero (Uint8Array is zero-initialized), which is
    // the zero-terminated-inside-a-fixed-field encoding the real FC uses.
    return dv;
  }

  it("round-trips time_boot_ms, file_crc, and a zero-terminated uri", () => {
    const dv = buildPayload(12345, 0xdeadbeef, "mftp:///component_metadata/general.json.xz");
    const m = decodeComponentMetadata(dv);
    expect(m.timeBootMs).toBe(12345);
    expect(m.fileCrc).toBe(0xdeadbeef);
    expect(m.uri).toBe("mftp:///component_metadata/general.json.xz");
  });

  it("trims trailing NUL padding out of the uri field", () => {
    const dv = buildPayload(0, 0, "https://example.com/p.json");
    const m = decodeComponentMetadata(dv);
    expect(m.uri).toBe("https://example.com/p.json");
    expect(m.uri.length).toBe("https://example.com/p.json".length);
  });

  it("returns the full 100-byte string when there is no trailing NUL", () => {
    const full = "a".repeat(100);
    const dv = buildPayload(0, 0, full);
    const m = decodeComponentMetadata(dv);
    expect(m.uri).toBe(full);
  });
});

describe("parameter metadata overlay precedence: live overlay wins", () => {
  it("a live (FC-served) entry overrides a bundled-floor entry for the same param", () => {
    const bundled = new Map<string, ParamMetadata>([
      ["MPC_XY_VEL_MAX", {
        name: "MPC_XY_VEL_MAX", humanName: "Max horizontal velocity",
        description: "bundled-floor description", range: { min: 0, max: 20 },
        defaultValue: 12,
      }],
    ]);
    const live = new Map<string, ParamMetadata>([
      ["MPC_XY_VEL_MAX", {
        name: "MPC_XY_VEL_MAX", humanName: "Max horizontal velocity",
        description: "FC-served description", range: { min: 0, max: 25 },
        defaultValue: 12,
      }],
      // A param the bundled floor does not know about at all (e.g. a
      // vehicle-specific custom firmware fork parameter).
      ["CUSTOM_PARAM", { name: "CUSTOM_PARAM", humanName: "Custom", description: "" }],
    ]);

    const merged = mergeMetaMaps(bundled, live);
    expect(merged.get("MPC_XY_VEL_MAX")?.description).toBe("FC-served description");
    expect(merged.get("MPC_XY_VEL_MAX")?.range).toEqual({ min: 0, max: 25 });
    expect(merged.has("CUSTOM_PARAM")).toBe(true);
  });

  it("an empty live overlay (fetch failed) never wipes the bundled floor", () => {
    const bundled = new Map<string, ParamMetadata>([
      ["MPC_XY_VEL_MAX", { name: "MPC_XY_VEL_MAX", humanName: "Max horizontal velocity", description: "d" }],
    ]);
    const merged = mergeMetaMaps(bundled, new Map());
    expect(merged.get("MPC_XY_VEL_MAX")?.description).toBe("d");
  });
});
