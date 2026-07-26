/**
 * MAVLink v2 frame encoder/decoder.
 *
 * Frame format (MAVLink v2):
 * [0]    STX        = 0xFD
 * [1]    payload_len
 * [2]    incompat_flags
 * [3]    compat_flags
 * [4]    seq
 * [5]    sysid
 * [6]    compid
 * [7-9]  msgid      (24-bit LE)
 * [10..] payload
 * [+0,+1] CRC-16   (over bytes [1..end_of_payload] + CRC_EXTRA)
 * [+2..+14] optional signature (13 bytes if incompat_flags & 0x01)
 */

import { crc16, CRC_EXTRA } from './crc';

export interface MavFrame {
  msgId: number;
  sysId: number;
  compId: number;
  seq: number;
  payload: DataView;
  payloadLen: number;
}

const STX = 0xfd;
const HEADER_LEN = 10;
const CRC_LEN = 2;

/**
 * Parse zero or more MAVLink v2 frames from a buffer.
 * Returns parsed frames and the remaining unprocessed bytes.
 */
export function parseFrames(buf: Uint8Array): { frames: MavFrame[]; remaining: Uint8Array } {
  const frames: MavFrame[] = [];
  let offset = 0;

  while (offset < buf.length) {
    const stxIdx = buf.indexOf(STX, offset);
    if (stxIdx < 0) {
      offset = buf.length;
      break;
    }
    offset = stxIdx;

    if (buf.length - offset < HEADER_LEN + CRC_LEN) break;

    const payloadLen = buf[offset + 1];
    const incompatFlags = buf[offset + 2];
    const hasSig = (incompatFlags & 0x01) !== 0;
    const frameLen = HEADER_LEN + payloadLen + CRC_LEN + (hasSig ? 13 : 0);

    if (buf.length - offset < frameLen) break;

    const msgId = buf[offset + 7] | (buf[offset + 8] << 8) | (buf[offset + 9] << 16);

    // CRC validation
    const crcExtra = CRC_EXTRA[msgId];
    if (crcExtra !== undefined) {
      const crcData = buf.slice(offset + 1, offset + HEADER_LEN + payloadLen);
      const seed = new Uint8Array([crcExtra]);
      const computed = crc16(new Uint8Array([...crcData, ...seed]));
      const received = buf[offset + HEADER_LEN + payloadLen] | (buf[offset + HEADER_LEN + payloadLen + 1] << 8);
      if (computed !== received) {
        offset++;
        continue;
      }
    }

    const payload = new DataView(buf.buffer, buf.byteOffset + offset + HEADER_LEN, payloadLen);
    frames.push({
      msgId,
      sysId: buf[offset + 5],
      compId: buf[offset + 6],
      seq: buf[offset + 4],
      payload,
      payloadLen,
    });
    offset += frameLen;
  }

  return { frames, remaining: buf.slice(offset) };
}

/**
 * Encode a MAVLink v2 frame.
 */
export function encodeFrame(
  msgId: number,
  payload: Uint8Array,
  sysId: number,
  compId: number,
  seq: number,
): Uint8Array {
  const payloadLen = payload.length;
  const frame = new Uint8Array(HEADER_LEN + payloadLen + CRC_LEN);
  frame[0] = STX;
  frame[1] = payloadLen;
  frame[2] = 0; // incompat_flags
  frame[3] = 0; // compat_flags
  frame[4] = seq & 0xff;
  frame[5] = sysId;
  frame[6] = compId;
  frame[7] = msgId & 0xff;
  frame[8] = (msgId >> 8) & 0xff;
  frame[9] = (msgId >> 16) & 0xff;
  frame.set(payload, HEADER_LEN);

  const crcData = frame.slice(1, HEADER_LEN + payloadLen);
  const crcExtra = CRC_EXTRA[msgId] ?? 0;
  const crcVal = crc16(new Uint8Array([...crcData, crcExtra]));
  frame[HEADER_LEN + payloadLen] = crcVal & 0xff;
  frame[HEADER_LEN + payloadLen + 1] = (crcVal >> 8) & 0xff;

  return frame;
}
