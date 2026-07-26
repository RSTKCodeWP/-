import { describe, it, expect } from 'vitest';
import { CRC_EXTRA, PAYLOAD_LENGTHS } from '@/lib/protocol/mavlink-crc-extra';

describe('CRC_EXTRA map', () => {
  it('has entry for HEARTBEAT (0)', () => {
    expect(CRC_EXTRA.get(0)).toBe(50);
  });

  it('has entry for ATTITUDE (30)', () => {
    expect(CRC_EXTRA.get(30)).toBe(39);
  });
});

describe('PAYLOAD_LENGTHS map', () => {
  it('has entry for HEARTBEAT (0) = 9', () => {
    expect(PAYLOAD_LENGTHS.get(0)).toBe(9);
  });

  it('has entry for ATTITUDE (30) = 28', () => {
    expect(PAYLOAD_LENGTHS.get(30)).toBe(28);
  });
});

describe('CRC_EXTRA and PAYLOAD_LENGTHS have same keys', () => {
  it('all message IDs are covered in both maps', () => {
    const crcKeys = Array.from(CRC_EXTRA.keys()).sort((a, b) => a - b);
    const payloadKeys = Array.from(PAYLOAD_LENGTHS.keys()).sort((a, b) => a - b);
    expect(crcKeys).toEqual(payloadKeys);
  });
});
