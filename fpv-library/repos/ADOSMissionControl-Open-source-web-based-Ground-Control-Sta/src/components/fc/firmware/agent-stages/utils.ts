/**
 * @module fc/firmware/agent-stages/utils
 * @description Pure helpers used by the ADOS agent flash flow:
 * byte-array concatenation, SHA-256 hex digest, and hex formatting.
 * Kept separate so they're easy to test without spinning up the
 * Web Flash card.
 * @license GPL-3.0-only
 */

export function concatBytes(parts: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const p of parts) total += p.byteLength;
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.byteLength;
  }
  return out;
}

export async function sha256Hex(data: Uint8Array): Promise<string> {
  // Copy into a fresh ArrayBuffer; some browsers reject views backed
  // by SharedArrayBuffer (which can occur when chunks come off a fetch
  // stream) when fed directly to subtle.digest.
  const buf = new ArrayBuffer(data.byteLength);
  new Uint8Array(buf).set(data);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function hex(n: number): string {
  return "0x" + n.toString(16).toUpperCase().padStart(4, "0");
}
