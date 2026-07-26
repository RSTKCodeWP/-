/**
 * SEI parser unit tests.
 *
 * Run with: npm run test:node
 *
 * Uses the Node.js built-in test runner instead of vitest because this
 * suite exercises low-level binary wire-format handling (H.264 SEI NAL
 * units with emulation-prevention bytes) where Node's BigInt and raw
 * Uint8Array semantics are simpler than the vitest happy-dom
 * environment. The `.node-test.ts` extension keeps vitest discovery
 * from picking it up; see vitest.config.ts `exclude`.
 *
 * Verifies findAdosSeiTimestampNs() against the wire format produced
 * by the agent-side SEI injector.
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  ADOS_SEI_UUID_BYTES,
  buildAdosSeiNalForTest,
  findAdosSeiTimestampNs,
} from "../sei-parser";

describe("findAdosSeiTimestampNs", () => {
  it("recovers a round-trip timestamp from a synthesised NAL", () => {
    const ts = BigInt("1731000123456789");
    const nal = buildAdosSeiNalForTest(ts);
    const recovered = findAdosSeiTimestampNs(nal);
    assert.equal(recovered, ts);
  });

  it("returns null on a buffer without any SEI NAL", () => {
    // Synthesise a non-VCL slice (NAL type 7 SPS) with no SEI.
    const fake = new Uint8Array([0x00, 0x00, 0x00, 0x01, 0x67, 0x42, 0x00, 0x1f]);
    assert.equal(findAdosSeiTimestampNs(fake), null);
  });

  it("returns null on a SEI carrying a different UUID", () => {
    // Build a user_data_unreg SEI but with the wrong UUID.
    const wrongUuid = new Uint8Array(16).fill(0xab);
    const ts = BigInt(42);
    const payload = new Uint8Array(24);
    payload.set(wrongUuid, 0);
    for (let j = 0; j < 8; j += 1) {
      payload[16 + j] = Number((ts >> BigInt(56 - j * 8)) & BigInt(0xff));
    }
    const seiMsg = new Uint8Array(2 + payload.length);
    seiMsg[0] = 0x05;
    seiMsg[1] = payload.length;
    seiMsg.set(payload, 2);
    const rbsp = new Uint8Array(seiMsg.length + 1);
    rbsp.set(seiMsg, 0);
    rbsp[rbsp.length - 1] = 0x80;
    const out = new Uint8Array(4 + 1 + rbsp.length);
    out.set([0x00, 0x00, 0x00, 0x01], 0);
    out[4] = 0x06;
    out.set(rbsp, 5);
    assert.equal(findAdosSeiTimestampNs(out), null);
  });

  it("survives a NAL with an emulation prevention byte in the timestamp", () => {
    // 0x00_00_00_01 in big-endian = 4_294_967_297. The middle two 0x00
    // bytes would form a start-code prefix; the encoder inserts an
    // 0x03 escape and the parser has to strip it.
    const ts = BigInt("4294967297");
    const nal = buildAdosSeiNalForTest(ts);
    // Confirm the round trip works even with emulation prevention applied.
    const recovered = findAdosSeiTimestampNs(nal);
    assert.equal(recovered, ts);
    // And confirm at least one 0x03 escape byte landed in the buffer.
    let sawEscape = false;
    for (let i = 0; i + 2 < nal.length; i += 1) {
      if (nal[i] === 0 && nal[i + 1] === 0 && nal[i + 2] === 3) {
        sawEscape = true;
        break;
      }
    }
    assert.equal(sawEscape, true, "expected emulation prevention escape byte");
  });

  it("finds the SEI when it is preceded by an SPS in the same access unit", () => {
    const ts = BigInt("9876543210");
    const sps = new Uint8Array([
      0x00, 0x00, 0x00, 0x01, 0x67, 0x42, 0x00, 0x1f, 0x96, 0x35,
    ]);
    const sei = buildAdosSeiNalForTest(ts);
    const concatenated = new Uint8Array(sps.length + sei.length);
    concatenated.set(sps, 0);
    concatenated.set(sei, sps.length);
    assert.equal(findAdosSeiTimestampNs(concatenated), ts);
  });

  it("handles back-to-back SEI messages and returns the first ADOS match", () => {
    // Manually build an RBSP containing a 4-byte user_data_unreg SEI
    // (non-ADOS payload) followed by the ADOS SEI.
    const ts = BigInt("12345000000");
    const filler = new Uint8Array([0x05, 0x04, 0x01, 0x02, 0x03, 0x04]); // type 5, size 4
    const adosPayload = new Uint8Array(24);
    adosPayload.set(ADOS_SEI_UUID_BYTES, 0);
    for (let j = 0; j < 8; j += 1) {
      adosPayload[16 + j] = Number((ts >> BigInt(56 - j * 8)) & BigInt(0xff));
    }
    const adosSei = new Uint8Array(2 + adosPayload.length);
    adosSei[0] = 0x05;
    adosSei[1] = adosPayload.length;
    adosSei.set(adosPayload, 2);

    const rbsp = new Uint8Array(filler.length + adosSei.length + 1);
    rbsp.set(filler, 0);
    rbsp.set(adosSei, filler.length);
    rbsp[rbsp.length - 1] = 0x80;

    // Wrap as a single SEI NAL with start code.
    const nal = new Uint8Array(4 + 1 + rbsp.length);
    nal.set([0x00, 0x00, 0x00, 0x01], 0);
    nal[4] = 0x06;
    nal.set(rbsp, 5);

    assert.equal(findAdosSeiTimestampNs(nal), ts);
  });
});
