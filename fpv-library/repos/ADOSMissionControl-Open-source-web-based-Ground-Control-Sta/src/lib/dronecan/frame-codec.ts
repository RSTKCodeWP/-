/**
 * @module frame-codec
 * @description 29-bit DroneCAN CAN ID layout and tail-byte helpers.
 *
 * The 29-bit identifier is laid out (LSB-first byte view, four bytes):
 *
 *   byte 0  bits 0..6  source node ID (7 bits, 0 = anonymous)
 *           bit 7      service flag (0 = message, 1 = service)
 *   byte 1  message broadcast:  low 8 bits of data type ID
 *           service frame:      bits 0..6 destination node, bit 7 request flag
 *           anonymous broadcast: bits 0..1 low data type ID,
 *                                bits 2..15 14-bit discriminator
 *   byte 2  message broadcast:  high 8 bits of data type ID
 *           service frame:      8-bit service type ID
 *           anonymous broadcast: discriminator high byte
 *   byte 3  bits 0..4  priority (5 bits, 0 = highest)
 *
 * The tail byte (last byte of every frame payload) carries the start-of-
 * transfer / end-of-transfer / toggle bits plus a 5-bit transfer ID.
 * @license GPL-3.0-only
 */

/** Default priority used by the GCS for outbound messages. */
export const DEFAULT_PRIORITY = 16;

/** Decoded view of a 29-bit DroneCAN identifier. */
export type DecodedCanId =
  | {
      kind: "message";
      priority: number;
      dataTypeId: number;
      srcNodeId: number;
    }
  | {
      kind: "service";
      priority: number;
      serviceTypeId: number;
      isRequest: boolean;
      dstNodeId: number;
      srcNodeId: number;
    }
  | {
      kind: "anonymous";
      priority: number;
      dataTypeId: number;
      discriminator: number;
    };

/** Decoded view of a frame tail byte. */
export interface DecodedTailByte {
  sot: boolean;
  eot: boolean;
  toggle: boolean;
  transferId: number;
}

function clampU5(value: number): number {
  return value & 0x1f;
}

function clampU7(value: number): number {
  return value & 0x7f;
}

function clampU8(value: number): number {
  return value & 0xff;
}

function clampU14(value: number): number {
  return value & 0x3fff;
}

function clampU16(value: number): number {
  return value & 0xffff;
}

/**
 * Pack a message broadcast 29-bit identifier.
 * Layout: priority(5) | service=0(1) | data_type_id(16) | source_node_id(7).
 */
export function encodeMessageId(
  priority: number,
  dataTypeId: number,
  sourceNodeId: number,
): number {
  const prio = clampU5(priority);
  const dtid = clampU16(dataTypeId);
  const src = clampU7(sourceNodeId);
  // 4-byte little-endian view: src is byte 0 low 7 bits, dtid lo at byte 1,
  // dtid hi at byte 2, priority at byte 3.
  const byte0 = src; // bit 7 = 0 (not a service)
  const byte1 = dtid & 0xff;
  const byte2 = (dtid >> 8) & 0xff;
  const byte3 = prio;
  return ((byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0) >>> 0;
}

/**
 * Pack a service-frame 29-bit identifier.
 * Layout: priority(5) | service=1(1) | request(1) | service_type_id(8)
 *       | destination_node_id(7) | source_node_id(7).
 */
export function encodeServiceId(
  priority: number,
  isRequest: boolean,
  serviceTypeId: number,
  dstNodeId: number,
  srcNodeId: number,
): number {
  const prio = clampU5(priority);
  const stid = clampU8(serviceTypeId);
  const dst = clampU7(dstNodeId);
  const src = clampU7(srcNodeId);
  const byte0 = src | 0x80; // bit 7 = 1 (service)
  const byte1 = dst | (isRequest ? 0x80 : 0x00);
  const byte2 = stid;
  const byte3 = prio;
  return ((byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0) >>> 0;
}

/**
 * Pack an anonymous message-broadcast 29-bit identifier.
 *
 * Anonymous frames carry a 14-bit discriminator hashed from the payload so
 * two nodes that simultaneously announce themselves can tell their frames
 * apart. The source node ID field is always zero.
 *
 * Layout: priority(5) | service=0(1) | discriminator(14)
 *       | data_type_id_low2(2) | source_node_id=0(7).
 */
export function encodeAnonymousMessageId(
  priority: number,
  dataTypeId: number,
  discriminator: number,
): number {
  const prio = clampU5(priority);
  const disc = clampU14(discriminator);
  const dtidLow2 = dataTypeId & 0x3;
  const byte0 = 0; // source node = 0, service flag = 0
  const byte1 = (dtidLow2 & 0x3) | ((disc & 0x3f) << 2);
  const byte2 = (disc >> 6) & 0xff;
  const byte3 = prio;
  return ((byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0) >>> 0;
}

/** Decode a 29-bit identifier into a tagged structure. */
export function decodeId(id: number): DecodedCanId {
  const uid = id >>> 0;
  const byte0 = uid & 0xff;
  const byte1 = (uid >>> 8) & 0xff;
  const byte2 = (uid >>> 16) & 0xff;
  const byte3 = (uid >>> 24) & 0x1f;

  const srcNodeId = byte0 & 0x7f;
  const isService = (byte0 & 0x80) !== 0;
  const priority = byte3;

  if (isService) {
    const dstNodeId = byte1 & 0x7f;
    const isRequest = (byte1 & 0x80) !== 0;
    const serviceTypeId = byte2;
    return {
      kind: "service",
      priority,
      serviceTypeId,
      isRequest,
      dstNodeId,
      srcNodeId,
    };
  }

  if (srcNodeId === 0) {
    const dtidLow2 = byte1 & 0x3;
    const disc = ((byte1 >> 2) & 0x3f) | (byte2 << 6);
    return {
      kind: "anonymous",
      priority,
      dataTypeId: dtidLow2,
      discriminator: disc & 0x3fff,
    };
  }

  const dataTypeId = byte1 | (byte2 << 8);
  return {
    kind: "message",
    priority,
    dataTypeId,
    srcNodeId,
  };
}

/**
 * Pack a frame tail byte.
 * Bit layout: SOT(1) | EOT(1) | TOGGLE(1) | reserved=0(0) | TRANSFER_ID(5).
 */
export function encodeTailByte(
  sot: boolean,
  eot: boolean,
  toggle: boolean,
  transferId: number,
): number {
  let byte = clampU5(transferId);
  if (toggle) byte |= 0x20;
  if (eot) byte |= 0x40;
  if (sot) byte |= 0x80;
  return byte;
}

/** Decode a frame tail byte. */
export function decodeTailByte(byte: number): DecodedTailByte {
  const b = byte & 0xff;
  return {
    sot: (b & 0x80) !== 0,
    eot: (b & 0x40) !== 0,
    toggle: (b & 0x20) !== 0,
    transferId: b & 0x1f,
  };
}
