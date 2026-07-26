/**
 * MAVLink FILE_TRANSFER_PROTOCOL (ID 110) encoder.
 *
 * The message carries a 251-byte FTP payload inside the 254-byte MAVLink
 * payload. The inner payload has a 12-byte header followed by up to 239
 * data bytes:
 *
 * | Offset | Type      | Field          |
 * |--------|-----------|----------------|
 * | 0      | uint16    | seq            |
 * | 2      | uint8     | session        |
 * | 3      | uint8     | opcode         |
 * | 4      | uint8     | size           |
 * | 5      | uint8     | req_opcode     |
 * | 6      | uint8     | burst_complete |
 * | 7      | uint8     | padding        |
 * | 8      | uint32    | offset         |
 * | 12     | uint8[239]| data           |
 *
 * The three MAVLink target fields (target_network, target_system,
 * target_component) precede the inner payload in the outer message.
 *
 * @module protocol/encoders/ftp
 */

import { buildFrame } from "./frame";

/** Maximum data bytes carried in one FTP payload (251 - 12 header). */
export const FTP_MAX_DATA = 239;

/** FTP inner-payload header size (bytes). */
const FTP_HEADER_SIZE = 12;

/** Offset of the FTP inner payload inside the outer message payload. */
const FTP_INNER_OFFSET = 3;

/**
 * Encode a FILE_TRANSFER_PROTOCOL request (msg ID 110).
 *
 * Builds an outbound request with req_opcode / burst_complete / padding set
 * to zero (those fields carry meaning only on ACK/NAK responses). Data is
 * truncated to the 239-byte payload limit.
 *
 * @param targetSys  - Target system id
 * @param targetComp - Target component id
 * @param session    - FTP session id (0 before OpenFileRO establishes one)
 * @param opcode     - FTP opcode (see FtpOpcode)
 * @param seq        - Message sequence number for resend detection
 * @param offset     - Byte offset into the file (or seek position)
 * @param size       - Meaning depends on opcode: path length for OpenFileRO,
 *                     max chunk size for reads, 0 for CalcFileCRC32/Terminate
 * @param data       - Request data bytes (path string, etc.), max 239
 */
export function encodeFileTransferProtocol(
  targetSys: number,
  targetComp: number,
  session: number,
  opcode: number,
  seq: number,
  offset: number,
  size: number,
  data: Uint8Array,
  sysId = 255,
  compId = 190,
): Uint8Array {
  const payload = new Uint8Array(254);
  const dv = new DataView(payload.buffer);

  // Outer MAVLink target fields.
  payload[0] = 0;          // target_network
  payload[1] = targetSys;  // target_system
  payload[2] = targetComp; // target_component

  // Inner FTP header.
  const base = FTP_INNER_OFFSET;
  dv.setUint16(base + 0, seq & 0xffff, true); // seq
  payload[base + 2] = session & 0xff;         // session
  payload[base + 3] = opcode & 0xff;          // opcode
  payload[base + 4] = size & 0xff;            // size
  payload[base + 5] = 0;                      // req_opcode
  payload[base + 6] = 0;                      // burst_complete
  payload[base + 7] = 0;                      // padding
  dv.setUint32(base + 8, offset >>> 0, true); // offset (unsigned 32-bit)

  // Inner data (bounded to 239 bytes).
  payload.set(data.subarray(0, FTP_MAX_DATA), base + FTP_HEADER_SIZE);

  return buildFrame(110, payload, sysId, compId);
}
