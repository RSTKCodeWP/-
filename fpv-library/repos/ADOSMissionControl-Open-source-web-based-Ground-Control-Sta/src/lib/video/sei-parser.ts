/**
 * H.264 SEI parser for ADOS air-side latency timestamps.
 *
 * Mirror of `ADOSDroneAgent/src/ados/services/video/sei_injector.py`
 * (build_sei_nal) and `local_tap.py` (parse_sei_latency_ns). The
 * injector wedges a SEI NAL unit before every VCL slice carrying a
 * 16-byte UUID + 8-byte big-endian nanosecond timestamp. The receiver
 * walks the bitstream for that exact UUID and reads the timestamp.
 *
 * Wire format (Annex-B, post emulation-prevention):
 *
 *     00 00 00 01      Annex-B start code (4-byte form)
 *     06               NAL header byte (forbidden_zero=0, nal_ref_idc=0, nal_unit_type=6 SEI)
 *     05 18            SEI message: payload type 5 (user_data_unreg), payload size 24
 *     <UUID 16 bytes>  ADOS_SEI_UUID
 *     <ns  8 bytes BE> time.time_ns() snapshot at frame encode time
 *     80               rbsp_trailing_bits (stop bit)
 *
 * Any byte sequence inside the NAL that would look like a start code
 * (00 00 00, 00 00 01, 00 00 02, 00 00 03) is escaped with a 03 byte
 * on the wire; the parser strips those before decoding the payload.
 */

// Byte-for-byte mirror of ADOS_LATENCY_SEI_UUID in sei_injector.py.
const ADOS_SEI_UUID = new Uint8Array([
  0xad, 0x05, 0x14, 0x0e, 0x9c, 0x2c, 0x4f, 0x6e,
  0x8a, 0x31, 0xf0, 0xe5, 0xb7, 0xd4, 0xc8, 0xa2,
]);

const NAL_TYPE_SEI = 6;
const SEI_PAYLOAD_TYPE_USER_DATA_UNREG = 5;

/**
 * Scan an Annex-B-framed buffer for the next start code. Returns
 * `{ offset, length }` where length is 3 or 4. Returns null when no
 * complete start code is found.
 */
function findStartCode(
  buf: Uint8Array,
  start: number,
): { offset: number; length: number } | null {
  const n = buf.length;
  let i = start;
  while (i < n) {
    if (
      i + 4 <= n &&
      buf[i] === 0 &&
      buf[i + 1] === 0 &&
      buf[i + 2] === 0 &&
      buf[i + 3] === 1
    ) {
      return { offset: i, length: 4 };
    }
    if (
      i + 3 <= n &&
      buf[i] === 0 &&
      buf[i + 1] === 0 &&
      buf[i + 2] === 1
    ) {
      return { offset: i, length: 3 };
    }
    i += 1;
  }
  return null;
}

/**
 * Strip emulation prevention bytes per H.264 §7.4.1.1. The encoder
 * inserts a `03` byte whenever the RBSP would otherwise contain a
 * `00 00 [00|01|02|03]` sequence; the parser removes them.
 */
function stripEmulationPrevention(ebsp: Uint8Array): Uint8Array {
  const out: number[] = [];
  const n = ebsp.length;
  let i = 0;
  while (i < n) {
    if (
      i + 2 < n &&
      ebsp[i] === 0 &&
      ebsp[i + 1] === 0 &&
      ebsp[i + 2] === 3
    ) {
      out.push(0, 0);
      i += 3;
    } else {
      out.push(ebsp[i]);
      i += 1;
    }
  }
  return new Uint8Array(out);
}

/**
 * Walk SEI messages inside an RBSP. SEI messages chain back-to-back
 * until rbsp_trailing_bits (`0x80`). Each message carries:
 *
 *   - payload_type: sum of consecutive 0xFF bytes plus one trailing byte
 *   - payload_size: same encoding
 *   - payload: payload_size bytes
 *
 * Returns the first ADOS-UUID payload's nanosecond timestamp, or null
 * when none is present.
 */
function findAdosTimestampInRbsp(rbsp: Uint8Array): bigint | null {
  const n = rbsp.length;
  let i = 0;
  while (i < n) {
    // Stop on rbsp_trailing_bits (0x80 ... 0x00 padding).
    if (rbsp[i] === 0x80) return null;

    // Decode payload_type
    let payloadType = 0;
    while (i < n && rbsp[i] === 0xff) {
      payloadType += 255;
      i += 1;
    }
    if (i >= n) return null;
    payloadType += rbsp[i];
    i += 1;

    // Decode payload_size
    let payloadSize = 0;
    while (i < n && rbsp[i] === 0xff) {
      payloadSize += 255;
      i += 1;
    }
    if (i >= n) return null;
    payloadSize += rbsp[i];
    i += 1;

    if (i + payloadSize > n) return null;

    if (
      payloadType === SEI_PAYLOAD_TYPE_USER_DATA_UNREG &&
      payloadSize >= 24
    ) {
      let uuidMatches = true;
      for (let j = 0; j < 16; j += 1) {
        if (rbsp[i + j] !== ADOS_SEI_UUID[j]) {
          uuidMatches = false;
          break;
        }
      }
      if (uuidMatches) {
        // Read 8-byte big-endian ns timestamp.
        let ns = BigInt(0);
        for (let j = 0; j < 8; j += 1) {
          ns = (ns << BigInt(8)) | BigInt(rbsp[i + 16 + j]);
        }
        return ns;
      }
    }
    i += payloadSize;
  }
  return null;
}

/**
 * Extract the ADOS latency timestamp from an Annex-B H.264 buffer.
 * Returns the nanosecond timestamp embedded by the drone-side SEI
 * injector, or null when the buffer contains no matching SEI NAL.
 *
 * Pure function — no DOM, no worker globals. Safe to use from main
 * thread, web worker, or unit test.
 */
export function findAdosSeiTimestampNs(
  annexB: Uint8Array,
): bigint | null {
  let cursor = 0;
  while (cursor < annexB.length) {
    const sc = findStartCode(annexB, cursor);
    if (!sc) return null;

    const nalStart = sc.offset + sc.length;
    if (nalStart >= annexB.length) return null;

    const next = findStartCode(annexB, nalStart);
    const nalEnd = next ? next.offset : annexB.length;
    const nalByte = annexB[nalStart];
    const nalType = nalByte & 0x1f;

    if (nalType === NAL_TYPE_SEI) {
      const ebsp = annexB.subarray(nalStart + 1, nalEnd);
      const rbsp = stripEmulationPrevention(ebsp);
      const ts = findAdosTimestampInRbsp(rbsp);
      if (ts !== null) return ts;
    }

    cursor = nalEnd;
  }
  return null;
}

/**
 * Encoder-side helper used by tests. Builds a single Annex-B-framed
 * SEI NAL carrying the given timestamp. Mirror of the Python
 * `build_sei_nal` so the parser can be tested without a live encoder.
 */
export function buildAdosSeiNalForTest(timestampNs: bigint): Uint8Array {
  const payload = new Uint8Array(24);
  payload.set(ADOS_SEI_UUID, 0);
  for (let j = 0; j < 8; j += 1) {
    payload[16 + j] = Number(
      (timestampNs >> BigInt(56 - j * 8)) & BigInt(0xff),
    );
  }
  const seiMsg = new Uint8Array(2 + payload.length);
  seiMsg[0] = SEI_PAYLOAD_TYPE_USER_DATA_UNREG;
  seiMsg[1] = payload.length;
  seiMsg.set(payload, 2);
  const rbsp = new Uint8Array(seiMsg.length + 1);
  rbsp.set(seiMsg, 0);
  rbsp[rbsp.length - 1] = 0x80; // rbsp_trailing_bits

  // Re-insert emulation prevention bytes the encoder would have added.
  const ebsp: number[] = [];
  const n = rbsp.length;
  let i = 0;
  while (i < n) {
    if (
      i + 2 < n &&
      rbsp[i] === 0 &&
      rbsp[i + 1] === 0 &&
      rbsp[i + 2] <= 3
    ) {
      ebsp.push(0, 0, 3, rbsp[i + 2]);
      i += 3;
    } else {
      ebsp.push(rbsp[i]);
      i += 1;
    }
  }

  const out = new Uint8Array(4 + 1 + ebsp.length);
  out.set([0x00, 0x00, 0x00, 0x01], 0);
  out[4] = 0x06; // NAL header SEI
  out.set(ebsp, 5);
  return out;
}

export const ADOS_SEI_UUID_BYTES = ADOS_SEI_UUID;
