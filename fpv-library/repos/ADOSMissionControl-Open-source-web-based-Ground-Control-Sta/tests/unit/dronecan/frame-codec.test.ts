/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRIORITY,
  decodeId,
  decodeTailByte,
  encodeAnonymousMessageId,
  encodeMessageId,
  encodeServiceId,
  encodeTailByte,
} from "@/lib/dronecan/frame-codec";

describe("dronecan frame-codec — message IDs", () => {
  it("round-trips a typical NodeStatus broadcast", () => {
    const id = encodeMessageId(DEFAULT_PRIORITY, 341, 11);
    const decoded = decodeId(id);
    expect(decoded.kind).toBe("message");
    if (decoded.kind === "message") {
      expect(decoded.priority).toBe(DEFAULT_PRIORITY);
      expect(decoded.dataTypeId).toBe(341);
      expect(decoded.srcNodeId).toBe(11);
    }
  });

  it("masks priority to 5 bits and node id to 7 bits", () => {
    const id = encodeMessageId(0xff, 0xffff, 0xff);
    const decoded = decodeId(id);
    expect(decoded.kind).toBe("message");
    if (decoded.kind === "message") {
      expect(decoded.priority).toBe(0x1f);
      expect(decoded.dataTypeId).toBe(0xffff);
      expect(decoded.srcNodeId).toBe(0x7f);
    }
  });
});

describe("dronecan frame-codec — service IDs", () => {
  it("round-trips a GetNodeInfo request from node 127 to node 14", () => {
    const id = encodeServiceId(DEFAULT_PRIORITY, true, 1, 14, 127);
    const decoded = decodeId(id);
    expect(decoded.kind).toBe("service");
    if (decoded.kind === "service") {
      expect(decoded.priority).toBe(DEFAULT_PRIORITY);
      expect(decoded.serviceTypeId).toBe(1);
      expect(decoded.isRequest).toBe(true);
      expect(decoded.dstNodeId).toBe(14);
      expect(decoded.srcNodeId).toBe(127);
    }
  });

  it("encodes responses with the request flag cleared", () => {
    const id = encodeServiceId(DEFAULT_PRIORITY, false, 5, 14, 127);
    const decoded = decodeId(id);
    if (decoded.kind === "service") {
      expect(decoded.isRequest).toBe(false);
    } else {
      throw new Error("expected service frame");
    }
  });
});

describe("dronecan frame-codec — anonymous IDs", () => {
  it("packs the discriminator into bits 2..15 of the second byte pair", () => {
    const id = encodeAnonymousMessageId(DEFAULT_PRIORITY, 1, 0x1234);
    const decoded = decodeId(id);
    expect(decoded.kind).toBe("anonymous");
    if (decoded.kind === "anonymous") {
      expect(decoded.discriminator).toBe(0x1234);
      expect(decoded.dataTypeId).toBe(1);
    }
  });

  it("clamps discriminator to 14 bits", () => {
    const id = encodeAnonymousMessageId(DEFAULT_PRIORITY, 0, 0xffff);
    const decoded = decodeId(id);
    if (decoded.kind === "anonymous") {
      expect(decoded.discriminator).toBe(0x3fff);
    } else {
      throw new Error("expected anonymous frame");
    }
  });
});

describe("dronecan frame-codec — tail byte", () => {
  it("round-trips SOT/EOT/TOGGLE and transfer id", () => {
    const tail = encodeTailByte(true, false, true, 15);
    const decoded = decodeTailByte(tail);
    expect(decoded.sot).toBe(true);
    expect(decoded.eot).toBe(false);
    expect(decoded.toggle).toBe(true);
    expect(decoded.transferId).toBe(15);
  });

  it("single-frame tail byte has SOT=1 EOT=1 TOGGLE=0", () => {
    const tail = encodeTailByte(true, true, false, 7);
    expect(tail & 0xe0).toBe(0xc0);
    expect(tail & 0x1f).toBe(7);
  });

  it("clamps transfer id to 5 bits", () => {
    const tail = encodeTailByte(false, false, false, 0xff);
    expect(decodeTailByte(tail).transferId).toBe(0x1f);
  });
});
