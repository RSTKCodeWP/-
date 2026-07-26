/**
 * MAVLink v2 frame builder and sequence counter.
 * @module protocol/encoders/frame
 */

import { CRC_EXTRA, crc16, crc16Accumulate } from "../mavlink-parser";
import type { MavlinkSigner } from "../mavlink-signer";

// ── Sequence Counter ────────────────────────────────────────

/** Global send-sequence counter, wraps at 255. */
let sequence = 0;

export function nextSequence(): number {
  const seq = sequence;
  sequence = (sequence + 1) & 0xff;
  return seq;
}

// ── Frame Builder ───────────────────────────────────────────

/**
 * Assemble a complete MAVLink v2 frame, optionally signed.
 *
 * When `signer` is supplied, the frame has the MAVLINK_IFLAG_SIGNED bit
 * set in INC_FLAGS and a 13-byte signature tail appended after the CRC.
 * When omitted, the frame is emitted unsigned exactly as before.
 *
 * @param msgId   - 24-bit message ID
 * @param payload - Serialised payload bytes
 * @param sysId   - Sender system ID (default 255 = GCS)
 * @param compId  - Sender component ID (default 190 = MAV_COMP_ID_MISSIONPLANNER)
 * @param seq     - Explicit sequence number (auto-incremented if omitted)
 * @param signer  - Optional MavlinkSigner. When provided, the frame is signed.
 * @returns Complete frame ready to send over the transport. Signed
 *          frames resolve asynchronously.
 */
export function buildFrame(
  msgId: number,
  payload: Uint8Array,
  sysId?: number,
  compId?: number,
  seq?: number,
): Uint8Array;
export function buildFrame(
  msgId: number,
  payload: Uint8Array,
  sysId: number | undefined,
  compId: number | undefined,
  seq: number | undefined,
  signer: MavlinkSigner,
): Promise<Uint8Array>;
export function buildFrame(
  msgId: number,
  payload: Uint8Array,
  sysId = 255,
  compId = 190,
  seq?: number,
  signer?: MavlinkSigner,
): Uint8Array | Promise<Uint8Array> {
  const payloadLen = payload.length;
  const unsignedLen = 10 + payloadLen + 2;
  const frame = new Uint8Array(signer ? unsignedLen + 13 : unsignedLen);

  // Header. INC_FLAGS bit 0 marks the frame as signed. The bit is part of
  // the hashed region, so it MUST be set before computing the signature.
  frame[0] = 0xfd;
  frame[1] = payloadLen;
  frame[2] = signer ? 0x01 : 0x00;
  frame[3] = 0;
  frame[4] = seq ?? nextSequence();
  frame[5] = sysId;
  frame[6] = compId;
  frame[7] = msgId & 0xff;
  frame[8] = (msgId >> 8) & 0xff;
  frame[9] = (msgId >> 16) & 0xff;

  frame.set(payload, 10);

  let crc = crc16(frame, 1, 9 + payloadLen);
  const extra = CRC_EXTRA.get(msgId);
  if (extra !== undefined) {
    crc = crc16Accumulate(extra, crc);
  }
  frame[10 + payloadLen] = crc & 0xff;
  frame[10 + payloadLen + 1] = (crc >> 8) & 0xff;

  if (!signer) {
    return frame;
  }

  // Signed path. The signed region is bytes 1..end-of-CRC (i.e. header
  // excluding STX, payload, CRC). Call the async signer and splice the
  // 13-byte tail onto the end of the frame buffer before returning.
  const signedRegion = frame.subarray(1, unsignedLen);
  return signer.sign(signedRegion).then((tail) => {
    frame.set(tail, unsignedLen);
    return frame;
  });
}
