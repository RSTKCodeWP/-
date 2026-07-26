/**
 * SLCAN ASCII codec over a byte transport.
 *
 * Implements the classic LAWICEL-style SLCAN dialect that ArduPilot speaks
 * when `CAN_SLCAN_CPORT != 0`:
 *
 *   - Open `O\r`, close `C\r`, listen-only `L\r`.
 *   - Speed `Sn\r` where n=0..8 maps to 10/20/50/100/125/250/500/800/1000 kbps.
 *   - Tx 11-bit `t<3 hex id><1 hex dlc><up to 16 hex>\r` → ack `z\r` or BEL.
 *   - Tx 29-bit `T<8 hex id><1 hex dlc><up to 16 hex>\r` → ack `Z\r` or BEL.
 *   - Rx 11-bit / 29-bit lines arrive unsolicited in the same format.
 *   - Command ack = CR (0x0D), error = BEL (0x07).
 *   - Tx ack lines (`z`, `Z`) are counted but not forwarded as frames.
 *
 * The transport runs on top of an existing byte channel (typically
 * WebSerialTransport) so tests can inject a mock without touching browser
 * APIs.
 */

import { WebSerialTransport } from "./webserial";
import type {
  CanFrame,
  CanTransport,
  CanTransportState,
  CanTransportStats,
} from "./can-transport";

/** Minimal contract the SLCAN codec needs from its underlying byte channel. */
export interface SlcanByteTransport {
  readonly isConnected: boolean;
  send(data: Uint8Array): void;
  on(event: "data", handler: (data: Uint8Array) => void): void;
  on(event: "close", handler: () => void): void;
  on(event: "error", handler: (err: Error) => void): void;
  off(event: "data", handler: (data: Uint8Array) => void): void;
  off(event: "close", handler: () => void): void;
  off(event: "error", handler: (err: Error) => void): void;
  disconnect(): Promise<void>;
}

const CR = 0x0d;
const BEL = 0x07;
const STEP_TIMEOUT_MS = 1500;

/** Maximum line we will buffer before discarding (defensive). */
const MAX_LINE_BYTES = 64;

const BITRATE_TO_ENUM: ReadonlyMap<number, number> = new Map([
  [10000, 0],
  [20000, 1],
  [50000, 2],
  [100000, 3],
  [125000, 4],
  [250000, 5],
  [500000, 6],
  [800000, 7],
  [1000000, 8],
]);

/** Resolve a bitrate in bits/s to its SLCAN speed enum (0..8). Throws on unknown. */
export function bitrateToEnum(bitrate: number): number {
  const v = BITRATE_TO_ENUM.get(bitrate);
  if (v === undefined) {
    throw new Error(
      `Unsupported SLCAN bitrate ${bitrate}; expected one of ${[...BITRATE_TO_ENUM.keys()].join(", ")}`,
    );
  }
  return v;
}

/** Format a CanFrame as an SLCAN ASCII line (no trailing CR). */
export function formatFrame(frame: CanFrame): string {
  if (frame.dlc < 0 || frame.dlc > 8) {
    throw new Error(`Invalid DLC ${frame.dlc}; classic CAN supports 0..8`);
  }
  if (frame.data.length !== frame.dlc) {
    throw new Error(
      `Frame data length ${frame.data.length} does not match DLC ${frame.dlc}`,
    );
  }
  const idHex = frame.extended
    ? frame.id.toString(16).toUpperCase().padStart(8, "0")
    : frame.id.toString(16).toUpperCase().padStart(3, "0");
  let payload = "";
  for (let i = 0; i < frame.data.length; i++) {
    payload += frame.data[i].toString(16).toUpperCase().padStart(2, "0");
  }
  const prefix = frame.extended ? "T" : "t";
  return `${prefix}${idHex}${frame.dlc.toString(16).toUpperCase()}${payload}`;
}

/**
 * Parse an SLCAN ASCII line (without the trailing CR) into a CanFrame.
 * Returns null if the line is not a frame line (e.g. ack or status).
 * Throws on malformed frame lines so the caller can count an rxError.
 */
export function parseFrameLine(line: string): CanFrame | null {
  if (line.length === 0) return null;
  const tag = line[0];
  if (tag !== "T" && tag !== "t") return null;
  const extended = tag === "T";
  const idWidth = extended ? 8 : 3;
  if (line.length < 1 + idWidth + 1) {
    throw new Error(`SLCAN frame line too short: "${line}"`);
  }
  const idStr = line.slice(1, 1 + idWidth);
  const dlcStr = line.slice(1 + idWidth, 1 + idWidth + 1);
  const id = parseInt(idStr, 16);
  const dlc = parseInt(dlcStr, 16);
  if (Number.isNaN(id) || Number.isNaN(dlc)) {
    throw new Error(`SLCAN frame line has non-hex id/dlc: "${line}"`);
  }
  if (dlc < 0 || dlc > 8) {
    throw new Error(`SLCAN frame DLC out of range: ${dlc}`);
  }
  const dataStr = line.slice(1 + idWidth + 1, 1 + idWidth + 1 + dlc * 2);
  if (dataStr.length !== dlc * 2) {
    throw new Error(`SLCAN frame data length mismatch for dlc=${dlc}: "${line}"`);
  }
  const data = new Uint8Array(dlc);
  for (let i = 0; i < dlc; i++) {
    const byte = parseInt(dataStr.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) {
      throw new Error(`SLCAN frame data byte ${i} is not hex: "${line}"`);
    }
    data[i] = byte;
  }
  return { id, extended, dlc, data };
}

/** Internal: state machine for the open/close command handshake. */
type AckWaiter = {
  resolve: () => void;
  reject: (err: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
  /** True if BEL (0x07) should reject instead of being treated as a no-op. */
  failOnBel: boolean;
};

/**
 * SLCAN transport. One per CAN bus connection.
 *
 * Construction does not open the underlying byte transport. The caller is
 * responsible for instantiating a byte transport and passing it in (so the
 * same WebSerialTransport instance can be shared across protocol switches —
 * e.g. MAVLink → SLCAN passthrough on the same physical port).
 */
export class SlcanTransport implements CanTransport {
  private byteTransport: SlcanByteTransport;
  private ownsByteTransport: boolean;
  private state: CanTransportState = "closed";
  private frameListeners = new Set<(frame: CanFrame) => void>();
  private stateListeners = new Set<(s: CanTransportState) => void>();
  private rxBuffer = "";
  private stats: CanTransportStats = {
    txCount: 0,
    rxCount: 0,
    txErrors: 0,
    rxErrors: 0,
  };
  private pendingAck: AckWaiter | null = null;
  private encoder = new TextEncoder();
  private decoder = new TextDecoder();

  // Pre-bound handlers so we can detach them in close().
  private handleData = (data: Uint8Array): void => this.onBytes(data);
  private handleClose = (): void => this.onByteClose();
  private handleError = (err: Error): void => this.onByteError(err);

  /**
   * @param byteTransport - underlying byte channel. Caller controls its
   *   lifetime unless `ownsByteTransport` is true, in which case close()
   *   will also disconnect the byte channel.
   * @param ownsByteTransport - if true, close() disconnects the byte channel.
   */
  constructor(byteTransport: SlcanByteTransport, ownsByteTransport = false) {
    this.byteTransport = byteTransport;
    this.ownsByteTransport = ownsByteTransport;
  }

  /**
   * Convenience constructor: opens a new WebSerialTransport at 115200 baud
   * (USB-CDC ignores the baud rate so the value is cosmetic), then runs the
   * SLCAN open handshake. The created byte transport is owned and will be
   * disconnected on close().
   */
  static async openOverWebSerial(opts: {
    bitrate: number;
  }): Promise<SlcanTransport> {
    const byte = new WebSerialTransport();
    await byte.connect(115200);
    const slcan = new SlcanTransport(byte, true);
    try {
      await slcan.open(opts);
    } catch (err) {
      await byte.disconnect().catch(() => {});
      throw err;
    }
    return slcan;
  }

  getState(): CanTransportState {
    return this.state;
  }

  getStats(): CanTransportStats {
    return { ...this.stats };
  }

  onFrame(cb: (frame: CanFrame) => void): () => void {
    this.frameListeners.add(cb);
    return () => this.frameListeners.delete(cb);
  }

  onState(cb: (s: CanTransportState) => void): () => void {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }

  /**
   * Bring the bus online. Sends a defensive close, sets the speed, then
   * issues the open command. Rejects on BEL or step timeout.
   */
  async open(opts: { bitrate: number }): Promise<void> {
    if (this.state === "open" || this.state === "opening") {
      throw new Error(`Cannot open SLCAN transport in state "${this.state}"`);
    }
    const speed = bitrateToEnum(opts.bitrate);
    this.setState("opening");
    this.attachByteListeners();
    try {
      // Defensive close. The adapter may have been left in O state from a
      // previous session; the BEL we get back is harmless, ignore it.
      await this.runStep("C\r", { failOnBel: false });
      // Set bitrate.
      await this.runStep(`S${speed}\r`, { failOnBel: true });
      // Open the channel.
      await this.runStep("O\r", { failOnBel: true });
      this.setState("open");
    } catch (err) {
      this.detachByteListeners();
      this.setState("error");
      throw err;
    }
  }

  /**
   * Send a frame. Writes the formatted ASCII line + CR to the byte channel.
   * Does not wait for the per-frame ack (`z\r` / `Z\r`); those arrive
   * asynchronously and are counted in stats. Awaiting per-frame would gate
   * throughput to one frame per round-trip.
   */
  async send(frame: CanFrame): Promise<void> {
    if (this.state !== "open") {
      throw new Error(`Cannot send while SLCAN state is "${this.state}"`);
    }
    const line = formatFrame(frame);
    this.byteTransport.send(this.encoder.encode(line + "\r"));
    this.stats.txCount += 1;
  }

  /** Close the bus and (if owned) the underlying byte transport. */
  async close(): Promise<void> {
    if (this.state === "closed") return;
    // Best-effort close command; ignore failures so we always tear down.
    if (this.state === "open") {
      try {
        await this.runStep("C\r", { failOnBel: false });
      } catch {
        // ignore — channel may already be gone
      }
    }
    this.detachByteListeners();
    if (this.ownsByteTransport) {
      await this.byteTransport.disconnect().catch(() => {});
    }
    this.setState("closed");
  }

  // ── internals ─────────────────────────────────────────────────────────

  private setState(next: CanTransportState): void {
    if (this.state === next) return;
    this.state = next;
    for (const cb of this.stateListeners) {
      try {
        cb(next);
      } catch {
        // never let a listener crash the transport
      }
    }
  }

  private attachByteListeners(): void {
    this.byteTransport.on("data", this.handleData);
    this.byteTransport.on("close", this.handleClose);
    this.byteTransport.on("error", this.handleError);
  }

  private detachByteListeners(): void {
    this.byteTransport.off("data", this.handleData);
    this.byteTransport.off("close", this.handleClose);
    this.byteTransport.off("error", this.handleError);
  }

  private onByteClose(): void {
    if (this.state !== "closed") {
      this.setState("error");
    }
    if (this.pendingAck) {
      const w = this.pendingAck;
      this.pendingAck = null;
      clearTimeout(w.timeout);
      w.reject(new Error("Byte transport closed during SLCAN command"));
    }
  }

  private onByteError(err: Error): void {
    this.setState("error");
    if (this.pendingAck) {
      const w = this.pendingAck;
      this.pendingAck = null;
      clearTimeout(w.timeout);
      w.reject(err);
    }
  }

  /**
   * Send a command and wait for the next ack byte. failOnBel=true treats
   * BEL as a rejection; failOnBel=false treats BEL as a no-op and waits for
   * the next CR (used for defensive close where the adapter may not have
   * been in an openable state).
   */
  private runStep(
    command: string,
    opts: { failOnBel: boolean },
  ): Promise<void> {
    if (this.pendingAck) {
      return Promise.reject(
        new Error("Cannot issue SLCAN command while another is pending"),
      );
    }
    return new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingAck = null;
        reject(new Error(`SLCAN command "${command.trim()}" timed out`));
      }, STEP_TIMEOUT_MS);
      this.pendingAck = {
        resolve,
        reject,
        timeout,
        failOnBel: opts.failOnBel,
      };
      try {
        this.byteTransport.send(this.encoder.encode(command));
      } catch (err) {
        this.pendingAck = null;
        clearTimeout(timeout);
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }

  /** Resolve or reject the pending command waiter on an ack/BEL byte. */
  private resolveAck(failed: boolean): void {
    if (!this.pendingAck) return;
    const w = this.pendingAck;
    this.pendingAck = null;
    clearTimeout(w.timeout);
    if (failed && w.failOnBel) {
      w.reject(new Error("SLCAN adapter returned BEL"));
    } else {
      w.resolve();
    }
  }

  /** Process bytes from the underlying byte channel. */
  private onBytes(data: Uint8Array): void {
    // Walk the buffer byte-by-byte: BEL is a singleton ack token; CR closes
    // the current ASCII line.
    for (let i = 0; i < data.length; i++) {
      const b = data[i];
      if (b === BEL) {
        if (this.pendingAck) {
          this.resolveAck(true);
        } else {
          this.stats.rxErrors += 1;
        }
        continue;
      }
      if (b === CR) {
        this.handleLine(this.rxBuffer);
        this.rxBuffer = "";
        continue;
      }
      // Append printable / hex byte to the line buffer.
      if (this.rxBuffer.length >= MAX_LINE_BYTES) {
        // Pathological input — drop and count.
        this.rxBuffer = "";
        this.stats.rxErrors += 1;
        continue;
      }
      this.rxBuffer += String.fromCharCode(b);
    }
  }

  /** Process one complete ASCII line (CR-stripped). */
  private handleLine(line: string): void {
    if (line.length === 0) {
      // Bare CR is the command ACK.
      if (this.pendingAck) this.resolveAck(false);
      return;
    }
    const tag = line[0];
    if (tag === "z" || tag === "Z") {
      // Per-frame Tx ack. Counted as a tx success indicator; not forwarded.
      // The pending command waiter (if any) also resolves on this token —
      // some adapters terminate Tx ack with CR which already woke the
      // waiter above; this branch is defensive.
      return;
    }
    if (tag === "T" || tag === "t") {
      let frame: CanFrame | null;
      try {
        frame = parseFrameLine(line);
      } catch {
        this.stats.rxErrors += 1;
        return;
      }
      if (!frame) return;
      frame.timestamp = Date.now();
      this.stats.rxCount += 1;
      for (const cb of this.frameListeners) {
        try {
          cb(frame);
        } catch {
          // swallow — bad subscriber shouldn't kill the bus
        }
      }
      return;
    }
    // Status / version / serial / other adapter chatter — ignore.
  }

  /** Decode helper exposed for tests that want to read a buffer fragment. */
  protected decodeForTest(bytes: Uint8Array): string {
    return this.decoder.decode(bytes);
  }
}
