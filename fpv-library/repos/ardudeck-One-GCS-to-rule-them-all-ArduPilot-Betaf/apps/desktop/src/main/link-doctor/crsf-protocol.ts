/**
 * Minimal CRSF (Crossfire) protocol codec.
 *
 * Two consumers:
 *  - the Link Doctor stream classifier, which validates CRSF framing to tell
 *    "ELRS module still in Normal link mode" apart from MAVLink and noise;
 *  - the ELRS module configurator, which speaks the CRSF parameter protocol
 *    over a TX module's USB port (the same protocol a handset's ELRS Lua
 *    script uses over the module bay), letting ArduDeck read and change
 *    Link Mode with no radio involved.
 *
 * Frame layout: [sync][len][type][payload...][crc8], where len counts
 * type + payload + crc. Extended frames (types 0x28-0x2D) carry
 * [dest][origin] as the first two payload bytes. CRC8 poly 0xD5 over
 * type + payload.
 */

export const CRSF_SYNC = 0xc8;
export const CRSF_ADDR_TRANSMITTER = 0xee;
export const CRSF_ADDR_HANDSET = 0xea;
export const CRSF_ADDR_BROADCAST = 0x00;

export const CRSF_FRAMETYPE_LINK_STATISTICS = 0x14;
export const CRSF_FRAMETYPE_DEVICE_PING = 0x28;
export const CRSF_FRAMETYPE_DEVICE_INFO = 0x29;
export const CRSF_FRAMETYPE_PARAM_ENTRY = 0x2b;
export const CRSF_FRAMETYPE_PARAM_READ = 0x2c;
export const CRSF_FRAMETYPE_PARAM_WRITE = 0x2d;

/** CRSF field types (subset used by ELRS). */
export const CRSF_FIELD_TEXT_SELECTION = 9;
export const CRSF_FIELD_INFO = 12;
export const CRSF_FIELD_COMMAND = 13;
export const CRSF_FIELD_FOLDER = 11;

export function crsfCrc8(data: Uint8Array, start = 0, end = data.length): number {
  let crc = 0;
  for (let i = start; i < end; i++) {
    crc ^= data[i]!;
    for (let bit = 0; bit < 8; bit++) {
      crc = crc & 0x80 ? ((crc << 1) ^ 0xd5) & 0xff : (crc << 1) & 0xff;
    }
  }
  return crc;
}

/** Build a CRSF frame: [sync][len][type + payload][crc8 over type+payload]. */
export function buildCrsfFrame(type: number, payload: Uint8Array, sync = CRSF_SYNC): Uint8Array {
  const frame = new Uint8Array(payload.length + 4);
  frame[0] = sync;
  frame[1] = payload.length + 2; // type + payload + crc
  frame[2] = type;
  frame.set(payload, 3);
  frame[frame.length - 1] = crsfCrc8(frame, 2, frame.length - 1);
  return frame;
}

/** Device ping (broadcast) - any CRSF device answers with DEVICE_INFO. */
export function buildDevicePing(): Uint8Array {
  return buildCrsfFrame(CRSF_FRAMETYPE_DEVICE_PING, new Uint8Array([CRSF_ADDR_BROADCAST, CRSF_ADDR_HANDSET]));
}

export function buildParamRead(fieldIndex: number, chunk: number): Uint8Array {
  return buildCrsfFrame(
    CRSF_FRAMETYPE_PARAM_READ,
    new Uint8Array([CRSF_ADDR_TRANSMITTER, CRSF_ADDR_HANDSET, fieldIndex, chunk]),
  );
}

export function buildParamWrite(fieldIndex: number, value: number): Uint8Array {
  return buildCrsfFrame(
    CRSF_FRAMETYPE_PARAM_WRITE,
    new Uint8Array([CRSF_ADDR_TRANSMITTER, CRSF_ADDR_HANDSET, fieldIndex, value]),
  );
}

export interface CrsfFrame {
  /** Frame type byte (e.g. 0x29 DEVICE_INFO). */
  type: number;
  /** type + payload, CRC stripped. body[0] is the type byte. */
  body: Uint8Array;
}

/** Bytes that legitimately start a CRSF frame (sync or device addresses). */
const CRSF_SYNC_BYTES = new Set([0xc8, 0xee, 0xea, 0xec]);

/**
 * Extract CRC-valid CRSF frames from a byte buffer. Returns the frames and
 * the number of bytes consumed (so a streaming caller can keep the tail).
 * Only known sync/address bytes are treated as frame candidates; anything
 * else is skipped one byte at a time, so junk with a large fake length
 * cannot stall the scan.
 */
export function extractCrsfFrames(buffer: Uint8Array): { frames: CrsfFrame[]; consumed: number } {
  const frames: CrsfFrame[] = [];
  let i = 0;
  let consumed = 0;
  while (i + 4 <= buffer.length) {
    const len = buffer[i + 1]!;
    if (CRSF_SYNC_BYTES.has(buffer[i]!) && len >= 2 && len <= 62) {
      const end = i + 2 + len;
      if (end > buffer.length) break; // incomplete tail - wait for more bytes
      const crc = crsfCrc8(buffer, i + 2, end - 1);
      if (crc === buffer[end - 1]) {
        frames.push({ type: buffer[i + 2]!, body: buffer.slice(i + 2, end - 1) });
        i = end;
        consumed = i;
        continue;
      }
    }
    i += 1;
    consumed = i;
  }
  return { frames, consumed };
}

export interface CrsfDeviceInfo {
  name: string;
  fieldCount: number;
}

/** Parse a DEVICE_INFO frame body (type + [dest][origin][name\0][serial u32][hw u32][sw u32][fieldCount][paramVersion]). */
export function parseDeviceInfo(body: Uint8Array): CrsfDeviceInfo | null {
  // body: [type][dest][origin][name...\0][12 bytes versions][fieldCount][paramVer]
  const p = body.subarray(3);
  const z = p.indexOf(0);
  if (z < 0 || p.length < z + 1 + 13) return null;
  const name = new TextDecoder().decode(p.subarray(0, z));
  const fieldCount = p[z + 1 + 12]!;
  return { name, fieldCount };
}

export interface CrsfParamChunk {
  fieldIndex: number;
  chunksRemaining: number;
  data: Uint8Array;
}

/** Parse a PARAM_ENTRY frame body: [type][dest][origin][fieldIndex][chunksRemaining][chunkData...]. */
export function parseParamEntryChunk(body: Uint8Array): CrsfParamChunk | null {
  if (body.length < 5) return null;
  return {
    fieldIndex: body[3]!,
    chunksRemaining: body[4]!,
    data: body.slice(5),
  };
}

export interface CrsfSelectField {
  index: number;
  parent: number;
  type: number;
  hidden: boolean;
  name: string;
  /** For TEXT_SELECTION fields. */
  options: string[];
  value: number;
  /** For INFO fields. */
  info: string;
}

/**
 * Decode an assembled parameter field (all chunks concatenated):
 * [parent][type|hidden][name\0][type-specific...].
 * TEXT_SELECTION: [options ';'-joined\0][value][min][max][default][units\0]
 * INFO: [value string\0]
 */
export function decodeField(index: number, data: Uint8Array): CrsfSelectField | null {
  if (data.length < 3) return null;
  const parent = data[0]!;
  const rawType = data[1]!;
  const type = rawType & 0x7f;
  const hidden = (rawType & 0x80) !== 0;
  const z = data.indexOf(0, 2);
  if (z < 0) return null;
  const name = new TextDecoder().decode(data.subarray(2, z));
  const field: CrsfSelectField = { index, parent, type, hidden, name, options: [], value: -1, info: '' };
  if (type === CRSF_FIELD_TEXT_SELECTION) {
    const z2 = data.indexOf(0, z + 1);
    if (z2 < 0) return field;
    field.options = new TextDecoder().decode(data.subarray(z + 1, z2)).split(';');
    field.value = z2 + 1 < data.length ? data[z2 + 1]! : -1;
  } else if (type === CRSF_FIELD_INFO) {
    const z2 = data.indexOf(0, z + 1);
    field.info = new TextDecoder().decode(data.subarray(z + 1, z2 < 0 ? data.length : z2));
  }
  return field;
}
