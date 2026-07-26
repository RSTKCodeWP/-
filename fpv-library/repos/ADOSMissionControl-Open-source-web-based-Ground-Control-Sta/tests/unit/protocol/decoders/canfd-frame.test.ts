import { describe, it, expect } from "vitest";

import { handleCanFdFrame } from "@/lib/protocol/handlers/can-handlers";
import type { CanFdFrameCallback } from "@/lib/protocol/types/callbacks";

/**
 * Synthesize a CANFD_FRAME (msg 387) wire payload and decode it through
 * the handler. The wire layout mirrors CAN_FRAME with a 64-byte data
 * buffer at offset 8 (72 bytes total).
 */
function makeCanFdPayload(opts: {
  id: number;
  targetSystem: number;
  targetComponent: number;
  bus: number;
  len: number;
  data: Uint8Array;
}): DataView {
  const buf = new ArrayBuffer(72);
  const dv = new DataView(buf);
  dv.setUint32(0, opts.id >>> 0, true);
  dv.setUint8(4, opts.targetSystem);
  dv.setUint8(5, opts.targetComponent);
  dv.setUint8(6, opts.bus);
  dv.setUint8(7, opts.len);
  for (let i = 0; i < 64; i++) {
    dv.setUint8(8 + i, opts.data[i] ?? 0);
  }
  return dv;
}

describe("handleCanFdFrame", () => {
  it("decodes id, target, bus, len, and the 64-byte data buffer", () => {
    const data = new Uint8Array(64);
    for (let i = 0; i < 64; i++) data[i] = (i * 3) & 0xff;
    const dv = makeCanFdPayload({
      id: 0xdeadbeef,
      targetSystem: 7,
      targetComponent: 42,
      bus: 2,
      len: 64,
      data,
    });

    const received: Parameters<CanFdFrameCallback>[0][] = [];
    const cb: CanFdFrameCallback = (evt) => received.push(evt);

    handleCanFdFrame(dv, [cb]);

    expect(received).toHaveLength(1);
    const evt = received[0];
    expect(evt.id).toBe(0xdeadbeef);
    expect(evt.targetSystem).toBe(7);
    expect(evt.targetComponent).toBe(42);
    expect(evt.bus).toBe(2);
    expect(evt.len).toBe(64);
    expect(evt.data.byteLength).toBe(64);
    for (let i = 0; i < 64; i++) {
      expect(evt.data[i]).toBe(data[i]);
    }
    expect(typeof evt.timestamp).toBe("number");
  });

  it("fans out to every registered callback", () => {
    const dv = makeCanFdPayload({
      id: 0x1,
      targetSystem: 1,
      targetComponent: 1,
      bus: 1,
      len: 0,
      data: new Uint8Array(64),
    });

    let aCount = 0;
    let bCount = 0;
    handleCanFdFrame(dv, [
      () => {
        aCount += 1;
      },
      () => {
        bCount += 1;
      },
    ]);

    expect(aCount).toBe(1);
    expect(bCount).toBe(1);
  });

  it("returns immediately when no callbacks are registered", () => {
    const dv = makeCanFdPayload({
      id: 0x1,
      targetSystem: 1,
      targetComponent: 1,
      bus: 1,
      len: 0,
      data: new Uint8Array(64),
    });

    expect(() => handleCanFdFrame(dv, [])).not.toThrow();
  });

  it("accepts a short logical len even when the data buffer is fully padded", () => {
    const data = new Uint8Array(64);
    data[0] = 0xaa;
    data[1] = 0xbb;
    const dv = makeCanFdPayload({
      id: 0x1,
      targetSystem: 1,
      targetComponent: 1,
      bus: 1,
      len: 2,
      data,
    });

    const received: Parameters<CanFdFrameCallback>[0][] = [];
    handleCanFdFrame(dv, [(evt) => received.push(evt)]);

    expect(received[0].len).toBe(2);
    expect(received[0].data[0]).toBe(0xaa);
    expect(received[0].data[1]).toBe(0xbb);
    expect(received[0].data[2]).toBe(0);
  });
});
