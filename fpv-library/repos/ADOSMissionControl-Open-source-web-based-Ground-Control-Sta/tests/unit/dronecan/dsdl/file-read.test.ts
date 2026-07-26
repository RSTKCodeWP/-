/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import {
  FILE_READ_MAX_DATA,
  decodeFileReadRequest,
  decodeFileReadResponse,
  encodeFileReadRequest,
  encodeFileReadResponse,
  isFileReadEof,
} from "@/lib/dronecan/dsdl/file-read";

describe("dsdl file.Read", () => {
  it("round-trips a request", () => {
    const original = { offset: BigInt(81920), path: "a.bin" };
    const buf = encodeFileReadRequest(original);
    const decoded = decodeFileReadRequest(buf);
    expect(decoded).toEqual(original);
  });

  it("encodes offset little-endian over 5 bytes", () => {
    const buf = encodeFileReadRequest({
      offset: BigInt("0x0102030405"),
      path: "",
    });
    expect(Array.from(buf.subarray(0, 5))).toEqual([
      0x05, 0x04, 0x03, 0x02, 0x01,
    ]);
  });

  it("round-trips a response with full 256-byte payload", () => {
    const data = new Uint8Array(FILE_READ_MAX_DATA);
    for (let i = 0; i < data.length; i++) data[i] = i & 0xff;
    const buf = encodeFileReadResponse({ error: { value: 0 }, data });
    const decoded = decodeFileReadResponse(buf);
    expect(decoded.error.value).toBe(0);
    expect(Array.from(decoded.data)).toEqual(Array.from(data));
    expect(isFileReadEof(decoded)).toBe(false);
  });

  it("flags EOF when data length is less than 256 bytes", () => {
    const data = new Uint8Array(100);
    const buf = encodeFileReadResponse({ error: { value: 0 }, data });
    const decoded = decodeFileReadResponse(buf);
    expect(isFileReadEof(decoded)).toBe(true);
  });

  it("flags EOF for an explicit zero-length response (file size multiple of 256)", () => {
    const buf = encodeFileReadResponse({
      error: { value: 0 },
      data: new Uint8Array(0),
    });
    const decoded = decodeFileReadResponse(buf);
    expect(decoded.data.length).toBe(0);
    expect(isFileReadEof(decoded)).toBe(true);
  });

  it("encodes signed negative error values", () => {
    const buf = encodeFileReadResponse({
      error: { value: -1 },
      data: new Uint8Array(0),
    });
    const decoded = decodeFileReadResponse(buf);
    expect(decoded.error.value).toBe(-1);
  });

  it("rejects oversize data payloads on encode", () => {
    expect(() =>
      encodeFileReadResponse({
        error: { value: 0 },
        data: new Uint8Array(FILE_READ_MAX_DATA + 1),
      }),
    ).toThrow();
  });
});
