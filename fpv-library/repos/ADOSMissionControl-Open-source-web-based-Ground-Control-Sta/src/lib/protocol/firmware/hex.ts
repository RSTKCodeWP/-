/**
 * Hex formatting helpers for firmware-flash protocol tracing.
 *
 * Shared by the serial/DFU flashers (TX/RX byte trace) and the flash
 * debug panel (raw-bytes view). Kept dependency-free so both the protocol
 * layer and the UI can import it.
 *
 * @module protocol/firmware/hex
 */

/** Space-separated two-digit hex, capped at `max` bytes with an overflow note. */
export function toHex(bytes: Uint8Array | number[], max = 64): string {
  const arr = bytes instanceof Uint8Array ? bytes : Uint8Array.from(bytes);
  const shown = arr.length > max ? arr.subarray(0, max) : arr;
  const parts: string[] = [];
  for (let i = 0; i < shown.length; i++) {
    parts.push(shown[i].toString(16).padStart(2, "0"));
  }
  let out = parts.join(" ");
  if (arr.length > max) out += ` … (+${arr.length - max} more)`;
  return out;
}

/** Classic hexdump: 8-digit offset, 16-byte hex columns, ASCII gutter. */
export function fullHexDump(bytes: Uint8Array | number[]): string {
  const arr = bytes instanceof Uint8Array ? bytes : Uint8Array.from(bytes);
  const lines: string[] = [];
  for (let off = 0; off < arr.length; off += 16) {
    const slice = arr.subarray(off, off + 16);
    const cols: string[] = [];
    let ascii = "";
    for (let i = 0; i < 16; i++) {
      if (i < slice.length) {
        const b = slice[i];
        cols.push(b.toString(16).padStart(2, "0"));
        ascii += b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : ".";
      } else {
        cols.push("  ");
        ascii += " ";
      }
      if (i === 7) cols.push("");
    }
    lines.push(`${off.toString(16).padStart(8, "0")}  ${cols.join(" ")}  |${ascii}|`);
  }
  return lines.join("\n");
}
