/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  encodeTransfer,
  TransferDecoder,
} from "@/lib/dronecan/transfer-coder";
import {
  DEFAULT_PRIORITY,
  decodeTailByte,
} from "@/lib/dronecan/frame-codec";
import { crcCcitt, transferCrc } from "@/lib/dronecan/crc";
import { DSDL_SIGNATURES } from "@/lib/dronecan/signatures";

const SIG = DSDL_SIGNATURES.NodeStatus;

describe("dronecan crc — self-check", () => {
  it("CRC-16-CCITT of '123456789' is 0x29B1", () => {
    const bytes = new TextEncoder().encode("123456789");
    expect(crcCcitt(bytes, 0xffff)).toBe(0x29b1);
  });

  it("transferCrc is deterministic", () => {
    const payload = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    const a = transferCrc(SIG, payload);
    const b = transferCrc(SIG, payload);
    expect(a).toBe(b);
  });
});

describe("dronecan transfer-coder — single-frame", () => {
  it("encodes a 7-byte payload into one frame with proper tail byte", () => {
    const payload = new Uint8Array([1, 2, 3, 4, 5, 6, 7]);
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 127,
      transferId: 3,
      signature: SIG,
    });
    expect(frames.length).toBe(1);
    expect(frames[0].data.length).toBe(8);
    const tail = decodeTailByte(frames[0].data[7]);
    expect(tail.sot).toBe(true);
    expect(tail.eot).toBe(true);
    expect(tail.toggle).toBe(false);
    expect(tail.transferId).toBe(3);
    expect(Array.from(frames[0].data.subarray(0, 7))).toEqual([
      1, 2, 3, 4, 5, 6, 7,
    ]);
  });

  it("encodes an empty payload into one frame with only the tail byte", () => {
    const frames = encodeTransfer(new Uint8Array(0), {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 1,
      isService: true,
      isRequest: true,
      dstNodeId: 14,
      srcNodeId: 127,
      transferId: 5,
      signature: DSDL_SIGNATURES.GetNodeInfo,
    });
    expect(frames.length).toBe(1);
    expect(frames[0].data.length).toBe(1);
    expect(decodeTailByte(frames[0].data[0]).transferId).toBe(5);
  });
});

describe("dronecan transfer-coder — multi-frame", () => {
  it("encodes and decodes a 300-byte payload end-to-end with CRC verify", () => {
    const payload = new Uint8Array(300);
    for (let i = 0; i < payload.length; i++) payload[i] = (i * 7 + 3) & 0xff;

    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 11,
      transferId: 9,
      signature: SIG,
    });

    // 300 bytes + 2 CRC = 302; first frame carries 5 + 2 = 7 + tail.
    // Remaining 295 bytes → ceil(295 / 7) = 43 frames. Total 44.
    expect(frames.length).toBe(44);

    // Toggle bit must alternate per frame, starting at 0.
    for (let i = 0; i < frames.length; i++) {
      const tail = decodeTailByte(frames[i].data[frames[i].data.length - 1]);
      expect(tail.toggle).toBe(i % 2 === 1);
      expect(tail.sot).toBe(i === 0);
      expect(tail.eot).toBe(i === frames.length - 1);
      expect(tail.transferId).toBe(9);
    }

    // Round-trip through the decoder.
    const decoder = new TransferDecoder({
      resolveSignature: () => SIG,
    });
    let received: Uint8Array | undefined;
    decoder.onTransfer((t) => {
      received = t.payload;
    });
    for (const f of frames) decoder.push(f.canId, f.data, 1000);
    expect(received).toBeDefined();
    expect(Array.from(received!)).toEqual(Array.from(payload));
  });

  it("decoder rejects a multi-frame transfer with bad CRC", () => {
    const payload = new Uint8Array(50);
    for (let i = 0; i < payload.length; i++) payload[i] = i;
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 11,
      transferId: 1,
      signature: SIG,
    });
    // Flip a byte in the first frame's payload (after the 2 CRC bytes).
    frames[0].data[3] ^= 0xff;
    const decoder = new TransferDecoder({ resolveSignature: () => SIG });
    let received = false;
    decoder.onTransfer(() => {
      received = true;
    });
    for (const f of frames) decoder.push(f.canId, f.data, 1000);
    expect(received).toBe(false);
  });

  it("decoder drops a transfer when toggle is wrong", () => {
    const payload = new Uint8Array(50);
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 11,
      transferId: 2,
      signature: SIG,
    });
    // Corrupt toggle on second frame.
    frames[1].data[frames[1].data.length - 1] ^= 0x20;
    const decoder = new TransferDecoder({ resolveSignature: () => SIG });
    let received = false;
    decoder.onTransfer(() => {
      received = true;
    });
    for (const f of frames) decoder.push(f.canId, f.data, 1000);
    expect(received).toBe(false);
  });

  it("ignores a fragment without a preceding SOT", () => {
    const decoder = new TransferDecoder({ resolveSignature: () => SIG });
    let received = false;
    decoder.onTransfer(() => {
      received = true;
    });
    // Encode a real multi-frame transfer then drop the first frame.
    const payload = new Uint8Array(30);
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 11,
      transferId: 4,
      signature: SIG,
    });
    for (let i = 1; i < frames.length; i++) {
      decoder.push(frames[i].canId, frames[i].data, 1000);
    }
    expect(received).toBe(false);
    expect(decoder.pendingCount).toBe(0);
  });

  it("flushes stale reassembly buffers after the timeout", () => {
    const decoder = new TransferDecoder({
      resolveSignature: () => SIG,
      reassemblyTimeoutMs: 100,
    });
    const payload = new Uint8Array(30);
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 341,
      srcNodeId: 11,
      transferId: 6,
      signature: SIG,
    });
    decoder.push(frames[0].canId, frames[0].data, 0);
    expect(decoder.pendingCount).toBe(1);
    // Advance well past the timeout; the next push triggers a stale sweep.
    decoder.push(frames[1].canId, frames[1].data, 5000);
    expect(decoder.pendingCount).toBe(0);
  });
});

describe("dronecan transfer-coder — single-frame decode", () => {
  it("decodes a single-frame service request immediately", () => {
    const payload = new Uint8Array([42]);
    const frames = encodeTransfer(payload, {
      priority: DEFAULT_PRIORITY,
      dataTypeId: 5,
      isService: true,
      isRequest: true,
      dstNodeId: 14,
      srcNodeId: 127,
      transferId: 1,
      signature: DSDL_SIGNATURES.RestartNode,
    });
    const decoder = new TransferDecoder();
    let received: { payload: Uint8Array; kind: string } | undefined;
    decoder.onTransfer((t) => {
      received = { payload: t.payload, kind: t.kind };
    });
    decoder.push(frames[0].canId, frames[0].data, 1000);
    expect(received).toBeDefined();
    expect(received!.kind).toBe("service");
    expect(Array.from(received!.payload)).toEqual([42]);
  });
});
