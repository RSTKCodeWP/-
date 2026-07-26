#!/usr/bin/env node
// Generates the PWA icon set (assets/icons/*.png) with no external
// dependencies — a plain RGBA raster is hand-encoded to PNG via zlib.
// Re-run with `node scripts/generate-icons.mjs` after changing the
// bolt polygon, palette, or icon sizes below.
import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "assets", "icons");
mkdirSync(outDir, { recursive: true });

const BG = [0x0d, 0x11, 0x17]; // --bg
const BOLT = [0xe0, 0x7b, 0x39]; // --orange

// Feather "zap" bolt outline, in a 24x24 viewBox.
const BOLT_POLY = [
  [13, 2], [3, 14], [12, 14], [11, 22], [21, 10], [12, 10],
];

function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    const intersects = (yi > y) !== (yj > y) &&
      x < (xj - xi) * (y - yi) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function renderIcon({ size, cornerRadius = 0, contentScale = 0.6 }) {
  const px = new Uint8Array(size * size * 4);
  const r = cornerRadius * size;

  // Scale + center the 24x24 bolt polygon within `contentScale` of the canvas.
  const scale = (size * contentScale) / 24;
  const offset = (size - 24 * scale) / 2;
  const poly = BOLT_POLY.map(([x, y]) => [x * scale + offset, y * scale + offset]);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;

      if (r > 0) {
        const cx = x < r ? r : x > size - r ? size - r : x;
        const cy = y < r ? r : y > size - r ? size - r : y;
        const dx = x - cx, dy = y - cy;
        const outsideCorner = (x < r || x > size - r) && (y < r || y > size - r) &&
          dx * dx + dy * dy > r * r;
        if (outsideCorner) {
          px[i + 3] = 0; // transparent corner
          continue;
        }
      }

      const inBolt = pointInPolygon(x + 0.5, y + 0.5, poly);
      const [cr, cg, cb] = inBolt ? BOLT : BG;
      px[i] = cr;
      px[i + 1] = cg;
      px[i + 2] = cb;
      px[i + 3] = 255;
    }
  }
  return px;
}

function crc32(buf) {
  let c;
  const table = crc32.table ??= (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = table[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBuf = Buffer.from(type, "ascii");
  const lenBuf = Buffer.alloc(4);
  lenBuf.writeUInt32BE(data.length, 0);
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([lenBuf, typeBuf, data, crcBuf]);
}

function encodePng(px, size) {
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0; // filter: none
    Buffer.from(px.buffer, y * size * 4, size * 4).copy(raw, y * (size * 4 + 1) + 1);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type: RGBA
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([
    signature,
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const targets = [
  { file: "icon-32.png", size: 32, cornerRadius: 0.18 },
  { file: "icon-192.png", size: 192, cornerRadius: 0.18 },
  { file: "icon-512.png", size: 512, cornerRadius: 0.18 },
  { file: "icon-512-maskable.png", size: 512, cornerRadius: 0, contentScale: 0.5 },
  { file: "apple-touch-icon.png", size: 180, cornerRadius: 0.22 },
];

for (const target of targets) {
  const px = renderIcon(target);
  const png = encodePng(px, target.size);
  writeFileSync(join(outDir, target.file), png);
  console.log(`wrote ${target.file} (${png.length} bytes)`);
}
