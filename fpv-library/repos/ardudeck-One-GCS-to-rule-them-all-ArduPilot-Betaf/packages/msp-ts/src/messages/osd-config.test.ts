import { describe, it, expect } from 'vitest';
import {
  decodeOsdPosition,
  encodeOsdPosition,
  serializeOsdElementPosition,
  OSD_VISIBLE_FLAG,
} from './config.js';

describe('OSD position encode/decode', () => {
  it('round-trips x/y/visible for SD coordinates', () => {
    for (const x of [0, 1, 15, 29, 30, 31]) {
      for (const y of [0, 1, 12, 15]) {
        for (const visible of [true, false]) {
          const packed = encodeOsdPosition(x, y, visible);
          const decoded = decodeOsdPosition(packed);
          expect(decoded.x).toBe(x);
          expect(decoded.y).toBe(y);
          expect(decoded.visible).toBe(visible);
        }
      }
    }
  });

  it('marks a visible element visible in all three profiles', () => {
    const packed = encodeOsdPosition(2, 3, true);
    // profiles 0,1,2 => 0x0800 | 0x1000 | 0x2000
    expect(packed & (OSD_VISIBLE_FLAG << 0)).toBeTruthy();
    expect(packed & (OSD_VISIBLE_FLAG << 1)).toBeTruthy();
    expect(packed & (OSD_VISIBLE_FLAG << 2)).toBeTruthy();
  });

  it('clears all visible flags when hidden', () => {
    const packed = encodeOsdPosition(2, 3, false);
    expect(packed & 0x3800).toBe(0);
  });

  it('matches the Betaflight default-position packing example', () => {
    // BF osd.js: defaultPosition: 0x800 | (10 << 5) | 2  for a visible element at x=2,y=10
    // Our encoder makes it visible in all profiles, so compare position bits only.
    const packed = encodeOsdPosition(2, 10, true);
    const positionBits = packed & 0x07ff; // strip profile-visibility bits 11-13
    expect(positionBits).toBe((10 << 5) | 2);
  });

  it('serializes a single element write as [index, posLo, posHi]', () => {
    const bytes = serializeOsdElementPosition(15, 2, 10, true);
    expect(bytes.length).toBe(3);
    expect(bytes[0]).toBe(15);
    const pos = bytes[1]! | (bytes[2]! << 8);
    expect(pos).toBe(encodeOsdPosition(2, 10, true));
  });
});
