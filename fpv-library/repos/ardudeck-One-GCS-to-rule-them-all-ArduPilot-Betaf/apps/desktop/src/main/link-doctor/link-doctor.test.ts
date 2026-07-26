/**
 * Tests for the Link Doctor stream classifier and CRSF codec.
 *
 * The CRSF fixtures are real bytes captured from a RadioMaster Ranger TX
 * module over USB (ELRS 4.0.0, Normal link mode, linked to a receiver) -
 * the exact stream that motivated this feature.
 */

import { describe, it, expect } from 'vitest';
import { classifyStream, classifyDatagrams } from './stream-classifier.js';
import {
  crsfCrc8,
  buildDevicePing,
  buildParamRead,
  buildParamWrite,
  extractCrsfFrames,
  parseDeviceInfo,
  parseParamEntryChunk,
  decodeField,
  CRSF_FRAMETYPE_DEVICE_PING,
} from './crsf-protocol.js';

/** Real capture: LINK_STATISTICS frames from the Ranger (Normal mode, LQ 100). */
const RANGER_LINKSTATS_CAPTURE = Uint8Array.from(
  'c8 0c 14 eb 00 64 0d 00 18 03 ec 62 0e 26 c8 0c 14 eb 00 64 0d 00 18 03 ed 64 0f 4a c8 0c 14 ec 00 64 0d 00 18 03 e8 64 0d 01'
    .split(' ')
    .map((h) => parseInt(h, 16)),
);

function fakeMavlink2Stream(frameCount: number): Uint8Array {
  const out: number[] = [];
  for (let i = 0; i < frameCount; i++) {
    out.push(0xfd, 9, 0, 0, i, 1, 1, 0, 0, 0);
    out.push(0, 0, 0, 0, 10, 3, 81, 4, 3); // payload (9)
    out.push(0x12, 0x34); // crc (classifier does not validate mavlink crc)
  }
  return Uint8Array.from(out);
}

describe('classifyStream', () => {
  it('recognises the real Ranger Normal-mode capture as ELRS CRSF link stats', () => {
    const d = classifyStream(RANGER_LINKSTATS_CAPTURE);
    expect(d.protocol).toBe('crsf');
    expect(d.elrsNormalMode).toBe(true);
    expect(d.counts.crsfFrames).toBe(3);
    expect(d.counts.crsfLinkStats).toBe(3);
    expect(d.suggestion).toMatch(/MAVLink link mode/i);
  });

  it('recognises a MAVLink2 stream', () => {
    const d = classifyStream(fakeMavlink2Stream(5));
    expect(d.protocol).toBe('mavlink2');
    expect(d.counts.mavlink2Frames).toBeGreaterThanOrEqual(4);
  });

  it('recognises NMEA GPS output', () => {
    const line = '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n';
    const d = classifyStream(new TextEncoder().encode(line + line + line));
    expect(d.protocol).toBe('nmea');
    expect(d.summary).toMatch(/GPS/);
  });

  it('recognises a debug console', () => {
    const text = 'I (1042) rc: init done\nI (1043) wifi: connecting to AP\nboot: chip revision 3\n'.repeat(4);
    const d = classifyStream(new TextEncoder().encode(text));
    expect(d.protocol).toBe('ascii-log');
  });

  it('reports silence for an empty sample', () => {
    const d = classifyStream(new Uint8Array(0));
    expect(d.protocol).toBe('silence');
  });

  it('suggests a baud problem for unrecognised binary data', () => {
    const junk = new Uint8Array(300);
    for (let i = 0; i < junk.length; i++) junk[i] = (i * 7 + 130) & 0xff;
    const d = classifyStream(junk);
    expect(d.protocol).toBe('unknown');
    expect(d.suggestion).toMatch(/baud/i);
  });
});

describe('classifyDatagrams - UDP video detection', () => {
  function rtpPacket(payloadType: number, seq: number): Uint8Array {
    const p = new Uint8Array(200);
    p[0] = 0x80; // V=2, no padding/extension/CSRC
    p[1] = payloadType & 0x7f;
    p[2] = (seq >> 8) & 0xff;
    p[3] = seq & 0xff;
    p.fill(0xab, 12);
    return p;
  }

  it('recognises an RTP stream (the wfb-ng ground station output)', () => {
    const d = classifyDatagrams([rtpPacket(97, 1), rtpPacket(97, 2), rtpPacket(97, 3), rtpPacket(97, 4)]);
    expect(d.protocol).toBe('rtp');
    expect(d.summary).toContain('97');
  });

  it('recognises MPEG-TS datagrams', () => {
    const ts = new Uint8Array(188 * 7);
    for (let i = 0; i < 7; i++) ts[i * 188] = 0x47;
    const d = classifyDatagrams([ts, ts, ts, ts]);
    expect(d.protocol).toBe('mpegts');
  });

  it('falls back to the byte-stream classifier for non-video data', () => {
    const hb = new Uint8Array([0xfd, 9, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 10, 3, 81, 4, 3, 0x12, 0x34]);
    const d = classifyDatagrams([hb, hb, hb, hb]);
    expect(d.protocol).toBe('mavlink2');
  });

  it('reports silence for no datagrams', () => {
    expect(classifyDatagrams([]).protocol).toBe('silence');
  });
});

describe('crsf-protocol codec', () => {
  it('crc8 matches a real frame from the Ranger capture', () => {
    // frame: c8 0c [14 eb 00 64 0d 00 18 03 ec 62 0e] 26
    const body = RANGER_LINKSTATS_CAPTURE.subarray(2, 13);
    expect(crsfCrc8(body)).toBe(0x26);
  });

  it('round-trips its own frames through the extractor', () => {
    const stream = new Uint8Array([...buildDevicePing(), ...buildParamRead(4, 0), ...buildParamWrite(4, 1)]);
    const { frames, consumed } = extractCrsfFrames(stream);
    expect(frames).toHaveLength(3);
    expect(frames[0]!.type).toBe(CRSF_FRAMETYPE_DEVICE_PING);
    expect(consumed).toBe(stream.length);
  });

  it('skips corrupt bytes and still finds valid frames', () => {
    const good = buildParamRead(4, 0);
    const stream = new Uint8Array([0x13, 0x37, ...good]);
    const { frames } = extractCrsfFrames(stream);
    expect(frames).toHaveLength(1);
  });

  it('parses DEVICE_INFO (RM Ranger, 33 fields)', () => {
    const name = new TextEncoder().encode('RM Ranger');
    const body = new Uint8Array([0x29, 0xea, 0xee, ...name, 0, ...new Array(12).fill(0), 33, 0]);
    const info = parseDeviceInfo(body);
    expect(info).toEqual({ name: 'RM Ranger', fieldCount: 33 });
  });

  it('assembles and decodes a Link Mode selection field', () => {
    const name = new TextEncoder().encode('Link Mode');
    const options = new TextEncoder().encode('Normal;MAVLink');
    const data = new Uint8Array([0, 9, ...name, 0, ...options, 0, 0, 0, 1, 0, 0]);
    const field = decodeField(4, data)!;
    expect(field.name).toBe('Link Mode');
    expect(field.options).toEqual(['Normal', 'MAVLink']);
    expect(field.value).toBe(0);
    expect(field.hidden).toBe(false);
  });

  it('parses a param entry chunk header', () => {
    const body = new Uint8Array([0x2b, 0xea, 0xee, 4, 2, 9, 9, 9]);
    const chunk = parseParamEntryChunk(body)!;
    expect(chunk.fieldIndex).toBe(4);
    expect(chunk.chunksRemaining).toBe(2);
    expect(Array.from(chunk.data)).toEqual([9, 9, 9]);
  });
});
