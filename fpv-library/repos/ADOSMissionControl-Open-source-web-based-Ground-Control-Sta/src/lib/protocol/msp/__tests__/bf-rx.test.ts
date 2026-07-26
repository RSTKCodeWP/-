/**
 * @module protocol/msp/bf-rx.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { decodeMspRxConfig, decodeMspRxMap } from "../decoders/config/rx";
import { encodeMspSetRxConfig, encodeMspSetRxMap } from "../encoders/config";

/** Build a raw MSP_RX_CONFIG payload with the leading fields + trailing bytes. */
function rawRxConfig(trailer: number[]): Uint8Array {
  const buf = new Uint8Array(12 + trailer.length);
  const dv = new DataView(buf.buffer);
  dv.setUint8(0, 9); // serialrxProvider = CRSF
  dv.setUint16(1, 1900, true); // maxcheck
  dv.setUint16(3, 1500, true); // midrc
  dv.setUint16(5, 1050, true); // mincheck
  dv.setUint8(7, 0); // spektrumSatBind
  dv.setUint16(8, 1000, true); // rxMinUsec
  dv.setUint16(10, 2000, true); // rxMaxUsec
  buf.set(trailer, 12);
  return buf;
}

describe("MSP_RX_CONFIG decode/encode (patch-and-echo)", () => {
  it("decodes the leading fields and keeps the raw payload", () => {
    const cfg = decodeMspRxConfig(new DataView(rawRxConfig([0xaa, 0xbb, 0xcc]).buffer));
    expect(cfg).toMatchObject({ serialrxProvider: 9, maxcheck: 1900, midrc: 1500, mincheck: 1050, rxMinUsec: 1000, rxMaxUsec: 2000 });
    expect(Array.from(cfg.raw.slice(12))).toEqual([0xaa, 0xbb, 0xcc]);
  });

  it("patches edited leading fields while echoing trailing bytes untouched", () => {
    const cfg = decodeMspRxConfig(new DataView(rawRxConfig([0xaa, 0xbb, 0xcc]).buffer));
    cfg.serialrxProvider = 2; // SBUS
    cfg.midrc = 1520;
    const out = encodeMspSetRxConfig(cfg);
    const dv = new DataView(out.buffer);
    expect(dv.getUint8(0)).toBe(2);
    expect(dv.getUint16(3, true)).toBe(1520);
    expect(dv.getUint16(1, true)).toBe(1900); // unedited leading field preserved
    expect(Array.from(out.slice(12))).toEqual([0xaa, 0xbb, 0xcc]); // trailer echoed
  });
});

describe("MSP_RX_MAP decode/encode", () => {
  it("round-trips the channel map bytes", () => {
    const map = decodeMspRxMap(new Uint8Array([0, 1, 3, 2, 4, 5, 6, 7]));
    expect(map).toEqual([0, 1, 3, 2, 4, 5, 6, 7]);
    expect(Array.from(encodeMspSetRxMap(map))).toEqual([0, 1, 3, 2, 4, 5, 6, 7]);
  });
});
