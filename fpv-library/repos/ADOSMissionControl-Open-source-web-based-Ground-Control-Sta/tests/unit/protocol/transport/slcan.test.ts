import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  SlcanTransport,
  bitrateToEnum,
  formatFrame,
  parseFrameLine,
  type SlcanByteTransport,
} from "@/lib/protocol/transport/slcan";
import type { CanFrame } from "@/lib/protocol/transport/can-transport";

// ── Mock byte transport ─────────────────────────────────────────────────

type DataHandler = (data: Uint8Array) => void;
type CloseHandler = () => void;
type ErrorHandler = (err: Error) => void;

class MockByteTransport implements SlcanByteTransport {
  isConnected = true;
  writes: Uint8Array[] = [];
  private dataHandlers = new Set<DataHandler>();
  private closeHandlers = new Set<CloseHandler>();
  private errorHandlers = new Set<ErrorHandler>();
  disconnected = false;

  send(data: Uint8Array): void {
    this.writes.push(data);
  }

  on(event: "data", handler: DataHandler): void;
  on(event: "close", handler: CloseHandler): void;
  on(event: "error", handler: ErrorHandler): void;
  on(event: string, handler: unknown): void {
    if (event === "data") this.dataHandlers.add(handler as DataHandler);
    else if (event === "close") this.closeHandlers.add(handler as CloseHandler);
    else if (event === "error") this.errorHandlers.add(handler as ErrorHandler);
  }

  off(event: "data", handler: DataHandler): void;
  off(event: "close", handler: CloseHandler): void;
  off(event: "error", handler: ErrorHandler): void;
  off(event: string, handler: unknown): void {
    if (event === "data") this.dataHandlers.delete(handler as DataHandler);
    else if (event === "close")
      this.closeHandlers.delete(handler as CloseHandler);
    else if (event === "error")
      this.errorHandlers.delete(handler as ErrorHandler);
  }

  async disconnect(): Promise<void> {
    this.disconnected = true;
    this.isConnected = false;
  }

  /** Test helper: deliver bytes as if they arrived on the wire. */
  deliver(bytes: Uint8Array | string): void {
    const arr =
      typeof bytes === "string" ? new TextEncoder().encode(bytes) : bytes;
    for (const h of this.dataHandlers) h(arr);
  }

  /** Test helper: read all writes as a single decoded string. */
  writesAsString(): string {
    const total = this.writes.reduce((acc, c) => acc + c.length, 0);
    const merged = new Uint8Array(total);
    let off = 0;
    for (const w of this.writes) {
      merged.set(w, off);
      off += w.length;
    }
    return new TextDecoder().decode(merged);
  }
}

/** Wait one microtask tick so async resolutions flush. */
const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

// ── Codec round-trip tests ──────────────────────────────────────────────

describe("SLCAN codec round-trip", () => {
  it("encodes and decodes a 29-bit extended frame", () => {
    const frame: CanFrame = {
      id: 0x1e808081,
      extended: true,
      dlc: 8,
      data: new Uint8Array([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]),
    };
    const line = formatFrame(frame);
    expect(line).toBe("T1E80808181122334455667788");
    const decoded = parseFrameLine(line);
    expect(decoded).not.toBeNull();
    expect(decoded!.id).toBe(0x1e808081);
    expect(decoded!.extended).toBe(true);
    expect(decoded!.dlc).toBe(8);
    expect(Array.from(decoded!.data)).toEqual(Array.from(frame.data));
  });

  it("encodes and decodes an 11-bit standard frame", () => {
    const frame: CanFrame = {
      id: 0x7ab,
      extended: false,
      dlc: 4,
      data: new Uint8Array([0xde, 0xad, 0xbe, 0xef]),
    };
    const line = formatFrame(frame);
    expect(line).toBe("t7AB4DEADBEEF");
    const decoded = parseFrameLine(line);
    expect(decoded).not.toBeNull();
    expect(decoded!.id).toBe(0x7ab);
    expect(decoded!.extended).toBe(false);
    expect(decoded!.dlc).toBe(4);
    expect(Array.from(decoded!.data)).toEqual([0xde, 0xad, 0xbe, 0xef]);
  });

  it("encodes a zero-DLC frame", () => {
    const frame: CanFrame = {
      id: 0x123,
      extended: false,
      dlc: 0,
      data: new Uint8Array(0),
    };
    expect(formatFrame(frame)).toBe("t1230");
  });

  it("rejects ack lines and other adapter chatter", () => {
    expect(parseFrameLine("z")).toBeNull();
    expect(parseFrameLine("Z")).toBeNull();
    expect(parseFrameLine("V1013")).toBeNull();
    expect(parseFrameLine("")).toBeNull();
  });

  it("throws on malformed frame lines", () => {
    expect(() => parseFrameLine("T1E")).toThrow();
    expect(() => parseFrameLine("t12G")).toThrow();
  });
});

// ── Bitrate enum ────────────────────────────────────────────────────────

describe("SLCAN bitrate-to-enum mapping", () => {
  it("maps all nine supported bitrates", () => {
    expect(bitrateToEnum(10000)).toBe(0);
    expect(bitrateToEnum(20000)).toBe(1);
    expect(bitrateToEnum(50000)).toBe(2);
    expect(bitrateToEnum(100000)).toBe(3);
    expect(bitrateToEnum(125000)).toBe(4);
    expect(bitrateToEnum(250000)).toBe(5);
    expect(bitrateToEnum(500000)).toBe(6);
    expect(bitrateToEnum(800000)).toBe(7);
    expect(bitrateToEnum(1000000)).toBe(8);
  });

  it("throws on unsupported bitrates", () => {
    expect(() => bitrateToEnum(300000)).toThrow(/Unsupported SLCAN bitrate/);
    expect(() => bitrateToEnum(0)).toThrow();
    expect(() => bitrateToEnum(2_000_000)).toThrow();
  });
});

// ── Open / close handshake ──────────────────────────────────────────────

describe("SlcanTransport open sequence", () => {
  let byte: MockByteTransport;
  let slcan: SlcanTransport;

  beforeEach(() => {
    byte = new MockByteTransport();
    slcan = new SlcanTransport(byte);
  });

  it("sends C\\r then S8\\r then O\\r and acks each step", async () => {
    const openPromise = slcan.open({ bitrate: 1_000_000 });

    // Defensive close — adapter answers with BEL because it wasn't open;
    // we treat that as a no-op.
    await flush();
    expect(byte.writesAsString()).toBe("C\r");
    byte.deliver("\x07"); // BEL ignored

    await flush();
    expect(byte.writesAsString()).toBe("C\rS8\r");
    byte.deliver("\r"); // ack for S8

    await flush();
    expect(byte.writesAsString()).toBe("C\rS8\rO\r");
    byte.deliver("\r"); // ack for O

    await openPromise;
    expect(slcan.getState()).toBe("open");
  });

  it("rejects when S8 returns BEL", async () => {
    const openPromise = slcan.open({ bitrate: 1_000_000 });
    await flush();
    byte.deliver("\r"); // ack for defensive close
    await flush();
    byte.deliver("\x07"); // BEL on S8 → fail

    await expect(openPromise).rejects.toThrow(/BEL/);
    expect(slcan.getState()).toBe("error");
  });

  it("rejects an unsupported bitrate before sending anything", async () => {
    await expect(slcan.open({ bitrate: 300000 })).rejects.toThrow(
      /Unsupported SLCAN bitrate/,
    );
    expect(byte.writes.length).toBe(0);
  });
});

// ── Frame send + ack streaming ─────────────────────────────────────────

describe("SlcanTransport frame I/O", () => {
  let byte: MockByteTransport;
  let slcan: SlcanTransport;

  beforeEach(async () => {
    byte = new MockByteTransport();
    slcan = new SlcanTransport(byte);
    const open = slcan.open({ bitrate: 1_000_000 });
    await flush();
    byte.deliver("\r"); // close ack (treat as no-op)
    await flush();
    byte.deliver("\r"); // S ack
    await flush();
    byte.deliver("\r"); // O ack
    await open;
    byte.writes = []; // reset after open
  });

  it("counts BEL bytes as rx errors", () => {
    byte.deliver("\x07\x07\x07");
    expect(slcan.getStats().rxErrors).toBe(3);
  });

  it("forwards decoded frames to subscribers", () => {
    const seen: CanFrame[] = [];
    const unsub = slcan.onFrame((f) => seen.push(f));
    byte.deliver("T1E80808181122334455667788\r");
    expect(seen.length).toBe(1);
    expect(seen[0].id).toBe(0x1e808081);
    expect(seen[0].extended).toBe(true);
    expect(Array.from(seen[0].data)).toEqual([
      0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
    ]);
    unsub();
  });

  it("handles partial-line delivery", () => {
    const seen: CanFrame[] = [];
    slcan.onFrame((f) => seen.push(f));
    // Same frame split across three chunks.
    byte.deliver("T1E80");
    byte.deliver("808181122334455");
    expect(seen.length).toBe(0);
    byte.deliver("667788\r");
    expect(seen.length).toBe(1);
  });

  it("ignores Tx ack tokens (z/Z) without emitting frames", () => {
    const seen: CanFrame[] = [];
    slcan.onFrame((f) => seen.push(f));
    byte.deliver("z\rZ\r");
    expect(seen.length).toBe(0);
  });

  it("counts malformed frame lines as rx errors, not crashes", () => {
    byte.deliver("T1E\r"); // truncated 29-bit frame
    expect(slcan.getStats().rxErrors).toBe(1);
  });

  it("sends 1000 frames without awaiting per-frame acks", async () => {
    const frame: CanFrame = {
      id: 0x1e000001,
      extended: true,
      dlc: 1,
      data: new Uint8Array([0xaa]),
    };
    const t0 = Date.now();
    for (let i = 0; i < 1000; i++) {
      await slcan.send(frame);
    }
    const elapsed = Date.now() - t0;
    expect(slcan.getStats().txCount).toBe(1000);
    expect(byte.writes.length).toBe(1000);
    // 1000 writes through an in-memory mock must be near-instant; we
    // assert an upper bound far above realistic delay to detect a
    // regression that introduces per-frame ack waits.
    expect(elapsed).toBeLessThan(500);
  });
});

// ── State transitions ──────────────────────────────────────────────────

describe("SlcanTransport state transitions", () => {
  it("emits opening → open → closed for a normal session", async () => {
    const byte = new MockByteTransport();
    const slcan = new SlcanTransport(byte);
    const transitions: string[] = [];
    slcan.onState((s) => transitions.push(s));

    const open = slcan.open({ bitrate: 500000 });
    await flush();
    byte.deliver("\r"); // close ack
    await flush();
    byte.deliver("\r"); // S ack
    await flush();
    byte.deliver("\r"); // O ack
    await open;

    const closing = slcan.close();
    await flush();
    byte.deliver("\r"); // close ack
    await closing;

    expect(transitions).toEqual(["opening", "open", "closed"]);
    expect(slcan.getState()).toBe("closed");
  });

  it("close() is a no-op when already closed", async () => {
    const byte = new MockByteTransport();
    const slcan = new SlcanTransport(byte);
    await slcan.close();
    expect(slcan.getState()).toBe("closed");
    expect(byte.writes.length).toBe(0);
  });
});

// Coverage for the MAVLink CAN_FORWARD transport lives in its own file
// alongside the SLCAN tests so this module stays focused on the SLCAN
// codec round-trip.

// vi is imported but only used for future expansion; keep the import
// available so adding spies later doesn't change the import block.
void vi;
