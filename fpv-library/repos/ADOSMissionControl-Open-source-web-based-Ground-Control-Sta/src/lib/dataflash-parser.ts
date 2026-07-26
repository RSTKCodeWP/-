/**
 * DataFlash .bin log parser for ArduPilot log files.
 * @license GPL-3.0-only
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FormatDef {
  type: number;
  length: number;
  name: string;
  formatStr: string;
  columns: string[];
}

export interface DataFlashMessage {
  type: number;
  name: string;
  timestamp?: number;
  fields: Record<string, number | string>;
}

export interface DataFlashLog {
  formats: Map<number, FormatDef>;
  messages: Map<string, DataFlashMessage[]>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const HEADER_0 = 0xa3;
export const HEADER_1 = 0x95;
export const FMT_TYPE = 128;

// FMT message is always 89 bytes total (header + type + payload = 2+1+86)
export const FMT_LENGTH = 89;

// Size in bytes for each format character
const FORMAT_SIZES: Record<string, number> = {
  b: 1, // int8
  B: 1, // uint8
  h: 2, // int16
  H: 2, // uint16
  i: 4, // int32
  I: 4, // uint32
  f: 4, // float32
  d: 8, // float64
  n: 4, // char[4]
  N: 16, // char[16]
  Z: 64, // char[64]
  c: 2, // int16 * 100
  C: 2, // uint16 * 100
  e: 4, // int32 * 100
  E: 4, // uint32 * 100
  L: 4, // int32 lat/lon * 1e7
  M: 1, // uint8 flight mode
  q: 8, // int64
  Q: 8, // uint64
};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Read a null-terminated string from a DataView. */
function readString(view: DataView, offset: number, length: number): string {
  let end = offset + length;
  // find null terminator
  for (let i = offset; i < end; i++) {
    if (view.getUint8(i) === 0) {
      end = i;
      break;
    }
  }
  let str = "";
  for (let i = offset; i < end; i++) {
    str += String.fromCharCode(view.getUint8(i));
  }
  return str;
}

/** Parse a single field value from the buffer at the given offset. */
export function readField(
  view: DataView,
  offset: number,
  fmt: string,
): { value: number | string; size: number } {
  switch (fmt) {
    case "b":
      return { value: view.getInt8(offset), size: 1 };
    case "B":
    case "M":
      return { value: view.getUint8(offset), size: 1 };
    case "h":
      return { value: view.getInt16(offset, true), size: 2 };
    case "H":
      return { value: view.getUint16(offset, true), size: 2 };
    case "i":
    case "L":
      return { value: view.getInt32(offset, true), size: 4 };
    case "I":
      return { value: view.getUint32(offset, true), size: 4 };
    case "f":
      return { value: view.getFloat32(offset, true), size: 4 };
    case "d":
      return { value: view.getFloat64(offset, true), size: 8 };
    case "c":
      return { value: view.getInt16(offset, true) / 100, size: 2 };
    case "C":
      return { value: view.getUint16(offset, true) / 100, size: 2 };
    case "e":
      return { value: view.getInt32(offset, true) / 100, size: 4 };
    case "E":
      return { value: view.getUint32(offset, true) / 100, size: 4 };
    case "n":
      return { value: readString(view, offset, 4), size: 4 };
    case "N":
      return { value: readString(view, offset, 16), size: 16 };
    case "Z":
      return { value: readString(view, offset, 64), size: 64 };
    case "q": {
      // Read as two 32-bit halves (little-endian) — stay within Number range
      const lo = view.getUint32(offset, true);
      const hi = view.getInt32(offset + 4, true);
      return { value: hi * 0x100000000 + lo, size: 8 };
    }
    case "Q": {
      const lo = view.getUint32(offset, true);
      const hi = view.getUint32(offset + 4, true);
      return { value: hi * 0x100000000 + lo, size: 8 };
    }
    default:
      // Unknown format — skip 1 byte
      return { value: 0, size: 1 };
  }
}

/** Parse a FMT message payload starting at `offset` (right after type byte). */
export function parseFmt(view: DataView, offset: number): FormatDef {
  const type = view.getUint8(offset);
  const length = view.getUint8(offset + 1);
  const name = readString(view, offset + 2, 4);
  const formatStr = readString(view, offset + 6, 16);
  const columnsRaw = readString(view, offset + 22, 64);
  const columns = columnsRaw ? columnsRaw.split(",") : [];
  return { type, length, name, formatStr, columns };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse a DataFlash .bin log file.
 *
 * Performs a two-pass approach:
 *   1. Scan for FMT messages to build the format table
 *   2. Re-scan to decode all messages using discovered formats
 *
 * In practice both passes happen in a single sweep — FMT messages are
 * processed immediately and subsequent messages decoded on-the-fly.
 */
export function parseDataFlashLog(buffer: ArrayBuffer): DataFlashLog {
  const view = new DataView(buffer);
  const len = buffer.byteLength;
  const formats = new Map<number, FormatDef>();
  const messages = new Map<string, DataFlashMessage[]>();

  let pos = 0;

  while (pos + 3 <= len) {
    // Scan for header bytes
    if (view.getUint8(pos) !== HEADER_0 || view.getUint8(pos + 1) !== HEADER_1) {
      // Lost sync — advance one byte and retry
      pos++;
      continue;
    }

    const msgType = view.getUint8(pos + 2);

    // --- FMT messages (self-describing, always 89 bytes) ---
    if (msgType === FMT_TYPE) {
      if (pos + FMT_LENGTH > len) break; // truncated
      const fmt = parseFmt(view, pos + 3);
      formats.set(fmt.type, fmt);

      // Also store the FMT message itself in the messages map
      const fmtMsg: DataFlashMessage = {
        type: FMT_TYPE,
        name: "FMT",
        fields: {
          Type: fmt.type,
          Length: fmt.length,
          Name: fmt.name,
          Format: fmt.formatStr,
          Columns: fmt.columns.join(","),
        },
      };
      let fmtList = messages.get("FMT");
      if (!fmtList) {
        fmtList = [];
        messages.set("FMT", fmtList);
      }
      fmtList.push(fmtMsg);

      pos += FMT_LENGTH;
      continue;
    }

    // --- All other messages ---
    const fmt = formats.get(msgType);
    if (!fmt) {
      // Unknown message type and no FMT yet — skip header + type and resync
      pos += 3;
      continue;
    }

    if (pos + fmt.length > len) break; // truncated

    // Payload starts after header (2) + type (1) = offset 3
    let fieldOffset = pos + 3;
    const fields: Record<string, number | string> = {};
    let timestamp: number | undefined;

    for (let i = 0; i < fmt.formatStr.length && i < fmt.columns.length; i++) {
      const ch = fmt.formatStr[i];
      const col = fmt.columns[i];
      const { value, size } = readField(view, fieldOffset, ch);
      fields[col] = value;

      if (col === "TimeUS" && typeof value === "number") {
        timestamp = value;
      }

      fieldOffset += size;
    }

    const msg: DataFlashMessage = {
      type: msgType,
      name: fmt.name,
      timestamp,
      fields,
    };

    let list = messages.get(fmt.name);
    if (!list) {
      list = [];
      messages.set(fmt.name, list);
    }
    list.push(msg);

    pos += fmt.length;
  }

  return { formats, messages };
}

/** Get all message type names present in a parsed log. */
export function getMessageTypes(log: DataFlashLog): string[] {
  return Array.from(log.messages.keys()).sort();
}

/** Get all messages of a given type name. */
export function getMessages(log: DataFlashLog, type: string): DataFlashMessage[] {
  return log.messages.get(type) ?? [];
}

/**
 * Extract a time series for a specific field from a message type.
 * Only includes entries that have both a TimeUS timestamp and a numeric value.
 */
export function getTimeSeries(
  log: DataFlashLog,
  type: string,
  field: string,
): { timeUs: number; value: number }[] {
  const msgs = log.messages.get(type);
  if (!msgs) return [];

  const series: { timeUs: number; value: number }[] = [];
  for (const msg of msgs) {
    if (msg.timestamp == null) continue;
    const val = msg.fields[field];
    if (typeof val !== "number") continue;
    series.push({ timeUs: msg.timestamp, value: val });
  }
  return series;
}

// Re-export streaming parser for backward compatibility
export {
  parseDataFlashLogStreaming,
  type StreamingProgressCallback,
  type StreamingParseOptions,
} from "./dataflash-streaming";
