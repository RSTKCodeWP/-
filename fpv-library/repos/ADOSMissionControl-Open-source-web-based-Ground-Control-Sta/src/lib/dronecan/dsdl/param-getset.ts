/**
 * @module param-getset
 * @description Codec for `uavcan.protocol.param.GetSet` (service type id 11).
 *
 * Request layout:
 *   uint13 index       (zero-extended to two bytes, little-endian)
 *   Value  value       (tagged union, see ValueTag)
 *   uint8[<=92] name   (tail-array, no length prefix when last)
 *
 * Response layout (same shape, four Value fields then name):
 *   Value  value
 *   Value  default_value
 *   NumericValue max_value
 *   NumericValue min_value
 *   uint8[<=92] name   (tail-array)
 *
 * Value tagged union (1-byte tag + payload):
 *   0 Empty
 *   1 Integer  int64  (8 bytes little-endian)
 *   2 Real     float32
 *   3 Boolean  uint8
 *   4 String   uint8[<=128]  (tail-array within Value)
 *
 * Implementation note: this codec covers the common index-walk usage pattern.
 * Tail-array string fields are encoded without an explicit length prefix when
 * they are the last field of the structure, matching DSDL tail array
 * optimisation rules.
 * @license GPL-3.0-only
 */

export enum ValueTag {
  Empty = 0,
  Integer = 1,
  Real = 2,
  Boolean = 3,
  String = 4,
}

export type Value =
  | { tag: ValueTag.Empty }
  | { tag: ValueTag.Integer; value: bigint }
  | { tag: ValueTag.Real; value: number }
  | { tag: ValueTag.Boolean; value: boolean }
  | { tag: ValueTag.String; value: string };

export interface ParamGetSetRequest {
  index: number;
  value: Value;
  name: string;
}

export interface ParamGetSetResponse {
  value: Value;
  default_value: Value;
  max_value: Value;
  min_value: Value;
  name: string;
}

const VAL_ZERO = BigInt(0);
const VAL_ONE = BigInt(1);
const VAL_FF = BigInt(0xff);
const VAL_EIGHT = BigInt(8);
const MASK_64 = (VAL_ONE << BigInt(64)) - VAL_ONE;
const TWO_POW_64 = VAL_ONE << BigInt(64);
const SIGN_BIT_64 = VAL_ONE << BigInt(63);

function encodeValue(value: Value): Uint8Array {
  switch (value.tag) {
    case ValueTag.Empty:
      return new Uint8Array([ValueTag.Empty]);
    case ValueTag.Integer: {
      const out = new Uint8Array(9);
      out[0] = ValueTag.Integer;
      const v = value.value;
      // Convert to signed 64-bit two's complement little-endian.
      let u = v & MASK_64;
      if (v < VAL_ZERO) u = (MASK_64 + VAL_ONE + v) & MASK_64;
      for (let i = 0; i < 8; i++) {
        out[1 + i] = Number(u & VAL_FF);
        u >>= VAL_EIGHT;
      }
      return out;
    }
    case ValueTag.Real: {
      const out = new Uint8Array(5);
      out[0] = ValueTag.Real;
      new DataView(out.buffer).setFloat32(1, value.value, true);
      return out;
    }
    case ValueTag.Boolean: {
      return new Uint8Array([ValueTag.Boolean, value.value ? 1 : 0]);
    }
    case ValueTag.String: {
      const strBytes = new TextEncoder().encode(value.value);
      if (strBytes.length > 128) {
        throw new Error("Value.String must be <= 128 bytes");
      }
      const out = new Uint8Array(1 + strBytes.length);
      out[0] = ValueTag.String;
      out.set(strBytes, 1);
      return out;
    }
  }
}

function decodeValueAt(
  buf: Uint8Array,
  off: number,
): { value: Value; next: number } {
  if (off >= buf.length) {
    return { value: { tag: ValueTag.Empty }, next: off };
  }
  const tag = buf[off] as ValueTag;
  switch (tag) {
    case ValueTag.Empty:
      return { value: { tag: ValueTag.Empty }, next: off + 1 };
    case ValueTag.Integer: {
      let u = VAL_ZERO;
      for (let i = 0; i < 8; i++) {
        u |= BigInt(buf[off + 1 + i] ?? 0) << BigInt(i * 8);
      }
      const value = (u & SIGN_BIT_64) !== VAL_ZERO ? u - TWO_POW_64 : u;
      return { value: { tag: ValueTag.Integer, value }, next: off + 9 };
    }
    case ValueTag.Real: {
      const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
      const v = dv.getFloat32(off + 1, true);
      return { value: { tag: ValueTag.Real, value: v }, next: off + 5 };
    }
    case ValueTag.Boolean: {
      const v = (buf[off + 1] ?? 0) !== 0;
      return { value: { tag: ValueTag.Boolean, value: v }, next: off + 2 };
    }
    case ValueTag.String: {
      const tail = buf.subarray(off + 1);
      return {
        value: { tag: ValueTag.String, value: new TextDecoder().decode(tail) },
        next: buf.length,
      };
    }
    default:
      return { value: { tag: ValueTag.Empty }, next: off + 1 };
  }
}

export function encodeParamGetSetRequest(req: ParamGetSetRequest): Uint8Array {
  const nameBytes = new TextEncoder().encode(req.name);
  if (nameBytes.length > 92) {
    throw new Error("ParamGetSetRequest.name must be <= 92 bytes");
  }
  const valueBytes = encodeValue(req.value);
  const out = new Uint8Array(2 + valueBytes.length + nameBytes.length);
  const idx = req.index & 0x1fff;
  out[0] = idx & 0xff;
  out[1] = (idx >> 8) & 0xff;
  out.set(valueBytes, 2);
  out.set(nameBytes, 2 + valueBytes.length);
  return out;
}

export function decodeParamGetSetRequest(buf: Uint8Array): ParamGetSetRequest {
  if (buf.length < 3) {
    throw new Error(`ParamGetSetRequest payload too short: ${buf.length}`);
  }
  const index = (buf[0] | (buf[1] << 8)) & 0x1fff;
  const { value, next } = decodeValueAt(buf, 2);
  const name = new TextDecoder().decode(buf.subarray(next));
  return { index, value, name };
}

export function encodeParamGetSetResponse(
  res: ParamGetSetResponse,
): Uint8Array {
  const nameBytes = new TextEncoder().encode(res.name);
  if (nameBytes.length > 92) {
    throw new Error("ParamGetSetResponse.name must be <= 92 bytes");
  }
  const parts = [
    encodeValue(res.value),
    encodeValue(res.default_value),
    encodeValue(res.max_value),
    encodeValue(res.min_value),
  ];
  let total = nameBytes.length;
  for (const p of parts) total += p.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    out.set(p, off);
    off += p.length;
  }
  out.set(nameBytes, off);
  return out;
}

export function decodeParamGetSetResponse(
  buf: Uint8Array,
): ParamGetSetResponse {
  let off = 0;
  const a = decodeValueAt(buf, off);
  off = a.next;
  // For string values the tail-array consumes the rest of the buffer; we
  // cannot continue decoding subsequent fields. In that case the remaining
  // fields are absent and default to Empty.
  if (off >= buf.length) {
    return {
      value: a.value,
      default_value: { tag: ValueTag.Empty },
      max_value: { tag: ValueTag.Empty },
      min_value: { tag: ValueTag.Empty },
      name: "",
    };
  }
  const b = decodeValueAt(buf, off);
  off = b.next;
  if (off >= buf.length) {
    return {
      value: a.value,
      default_value: b.value,
      max_value: { tag: ValueTag.Empty },
      min_value: { tag: ValueTag.Empty },
      name: "",
    };
  }
  const c = decodeValueAt(buf, off);
  off = c.next;
  if (off >= buf.length) {
    return {
      value: a.value,
      default_value: b.value,
      max_value: c.value,
      min_value: { tag: ValueTag.Empty },
      name: "",
    };
  }
  const d = decodeValueAt(buf, off);
  off = d.next;
  const name = new TextDecoder().decode(buf.subarray(off));
  return {
    value: a.value,
    default_value: b.value,
    max_value: c.value,
    min_value: d.value,
    name,
  };
}
