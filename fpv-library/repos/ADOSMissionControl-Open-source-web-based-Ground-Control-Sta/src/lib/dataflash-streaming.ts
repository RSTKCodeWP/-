/**
 * Streaming DataFlash .bin log parser for large files (>50MB).
 *
 * Processes the buffer in configurable-size chunks with progress callbacks,
 * yielding to the event loop between chunks so the UI stays responsive.
 *
 * @license GPL-3.0-only
 */

import type { FormatDef, DataFlashMessage, DataFlashLog } from "./dataflash-parser";
import { parseFmt, readField, HEADER_0, HEADER_1, FMT_TYPE, FMT_LENGTH } from "./dataflash-parser";

/** Progress callback for streaming parse — receives 0-1 progress fraction. */
export type StreamingProgressCallback = (progress: number) => void;

/** Options for the streaming parser. */
export interface StreamingParseOptions {
  /** Called with progress (0-1) during parsing. */
  onProgress?: StreamingProgressCallback;
  /** Size of each chunk to process per iteration (default: 1MB). */
  chunkSize?: number;
}

/**
 * Parse a DataFlash .bin log file in chunks, yielding to the event loop
 * between chunks so the UI stays responsive. Suitable for files >50MB.
 *
 * Same output as `parseDataFlashLog` but processes the buffer in
 * configurable-size chunks with progress callbacks.
 */
export async function parseDataFlashLogStreaming(
  buffer: ArrayBuffer,
  options: StreamingParseOptions = {},
): Promise<DataFlashLog> {
  const { onProgress, chunkSize = 1024 * 1024 } = options;
  const view = new DataView(buffer);
  const len = buffer.byteLength;
  const formats = new Map<number, FormatDef>();
  const messages = new Map<string, DataFlashMessage[]>();

  let pos = 0;
  let bytesProcessed = 0;
  let nextYield = chunkSize;

  while (pos + 3 <= len) {
    // Yield to event loop periodically
    if (bytesProcessed >= nextYield) {
      nextYield += chunkSize;
      onProgress?.(pos / len);
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    }

    // Scan for header bytes
    if (
      view.getUint8(pos) !== HEADER_0 ||
      view.getUint8(pos + 1) !== HEADER_1
    ) {
      pos++;
      bytesProcessed++;
      continue;
    }

    const msgType = view.getUint8(pos + 2);

    // --- FMT messages ---
    if (msgType === FMT_TYPE) {
      if (pos + FMT_LENGTH > len) break;
      const fmt = parseFmt(view, pos + 3);
      formats.set(fmt.type, fmt);

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

      bytesProcessed += FMT_LENGTH;
      pos += FMT_LENGTH;
      continue;
    }

    // --- All other messages ---
    const fmt = formats.get(msgType);
    if (!fmt) {
      pos += 3;
      bytesProcessed += 3;
      continue;
    }

    if (pos + fmt.length > len) break;

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

    bytesProcessed += fmt.length;
    pos += fmt.length;
  }

  onProgress?.(1);
  return { formats, messages };
}
