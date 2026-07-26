/**
 * @license GPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import { TransferIdAllocator } from "@/lib/dronecan/transfer-id";

describe("TransferIdAllocator", () => {
  it("rotates 0..31 then wraps to 0", () => {
    const a = new TransferIdAllocator();
    const key = { targetNodeId: 14, dataTypeId: 11, kind: "req" as const };
    const got: number[] = [];
    for (let i = 0; i < 33; i++) got.push(a.next(key));
    expect(got.slice(0, 32)).toEqual(Array.from({ length: 32 }, (_, i) => i));
    expect(got[32]).toBe(0);
  });

  it("maintains independent counters per (dst, type, kind) tuple", () => {
    const a = new TransferIdAllocator();
    expect(a.next({ targetNodeId: 14, dataTypeId: 11, kind: "req" })).toBe(0);
    expect(a.next({ targetNodeId: 14, dataTypeId: 11, kind: "req" })).toBe(1);
    expect(a.next({ targetNodeId: 14, dataTypeId: 11, kind: "resp" })).toBe(0);
    expect(a.next({ targetNodeId: 14, dataTypeId: 11, kind: "req" })).toBe(2);
    expect(a.next({ targetNodeId: 15, dataTypeId: 11, kind: "req" })).toBe(0);
    expect(a.next({ targetNodeId: 14, dataTypeId: 12, kind: "req" })).toBe(0);
  });

  it("peek does not advance the counter", () => {
    const a = new TransferIdAllocator();
    const k = { targetNodeId: 14, dataTypeId: 11, kind: "msg" as const };
    expect(a.peek(k)).toBe(0);
    expect(a.peek(k)).toBe(0);
    expect(a.next(k)).toBe(0);
    expect(a.peek(k)).toBe(1);
  });

  it("reset clears all counters", () => {
    const a = new TransferIdAllocator();
    const k = { targetNodeId: 14, dataTypeId: 11, kind: "req" as const };
    a.next(k);
    a.next(k);
    a.reset();
    expect(a.next(k)).toBe(0);
  });
});
