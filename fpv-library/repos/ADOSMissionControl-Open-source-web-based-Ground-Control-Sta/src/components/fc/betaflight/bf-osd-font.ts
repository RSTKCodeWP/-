/**
 * MAX7456 `.mcm` OSD font parser.
 *
 * A `.mcm` font file is a text file: a `MAX7456` header line followed, per
 * character, by 64 lines of 8 binary digits (one byte each). This parses it
 * into an array of 64-byte glyphs uploaded to the FC via MSP_OSD_CHAR_WRITE.
 *
 * @module fc/betaflight/bf-osd-font
 */

/** Bytes per OSD glyph (padded character data). */
export const OSD_GLYPH_BYTES = 64;
const LINES_PER_GLYPH = 64; // one 8-bit line = one byte

export interface ParsedMcmFont {
  glyphs: Uint8Array[];
}

/** Parse a MAX7456 `.mcm` font file into 64-byte glyphs. Throws on a malformed file. */
export function parseMcmFont(text: string): ParsedMcmFont {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
  if (lines.length === 0 || !/^MAX7456/i.test(lines[0])) {
    throw new Error("Not a MAX7456 .mcm font file (missing header)");
  }
  const body = lines.slice(1);
  if (body.length === 0 || body.length % LINES_PER_GLYPH !== 0) {
    throw new Error(`Malformed .mcm: ${body.length} data lines (expected a multiple of ${LINES_PER_GLYPH})`);
  }
  const count = body.length / LINES_PER_GLYPH;
  const glyphs: Uint8Array[] = [];
  for (let g = 0; g < count; g++) {
    const glyph = new Uint8Array(OSD_GLYPH_BYTES);
    for (let b = 0; b < LINES_PER_GLYPH; b++) {
      const bits = body[g * LINES_PER_GLYPH + b];
      if (!/^[01]{8}$/.test(bits)) {
        throw new Error(`Malformed glyph line ${g * LINES_PER_GLYPH + b}: "${bits}"`);
      }
      glyph[b] = parseInt(bits, 2);
    }
    glyphs.push(glyph);
  }
  return { glyphs };
}
