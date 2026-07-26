import { describe, it, expect } from 'vitest';
import {
  BOARD_PROFILES,
  detectBoardProfile,
  UNKNOWN_BOARD,
  getBoardProfileByName,
} from '@/lib/board-profiles';

describe('BOARD_PROFILES', () => {
  it('is a non-empty array', () => {
    expect(Array.isArray(BOARD_PROFILES)).toBe(true);
    expect(BOARD_PROFILES.length).toBeGreaterThan(0);
  });

  it('each profile has required fields (name, boardIds, timerGroups)', () => {
    for (const profile of BOARD_PROFILES) {
      expect(typeof profile.name).toBe('string');
      expect(profile.name.length).toBeGreaterThan(0);
      expect(Array.isArray(profile.boardIds)).toBe(true);
      expect(Array.isArray(profile.timerGroups)).toBe(true);
      expect(typeof profile.vendor).toBe('string');
      expect(typeof profile.outputCount).toBe('number');
    }
  });

  it('SpeedyBee F405 V3 profile exists', () => {
    const found = BOARD_PROFILES.find((p) => p.name.includes('SpeedyBee F405 V3'));
    expect(found).toBeDefined();
    expect(found!.vendor).toBe('SpeedyBee');
  });
});

describe('detectBoardProfile', () => {
  it('returns a matching profile for a known boardId', () => {
    // SpeedyBee F405 Wing has boardId 1032
    const profile = detectBoardProfile(1032);
    expect(profile.name).toContain('SpeedyBee F405 Wing');
  });

  it('returns UNKNOWN_BOARD for an unrecognized boardId', () => {
    const profile = detectBoardProfile(99999);
    expect(profile).toBe(UNKNOWN_BOARD);
    expect(profile.name).toBe('Unknown Board');
  });
});

describe('getBoardProfileByName', () => {
  it('returns profile for a known name', () => {
    const profile = getBoardProfileByName('SpeedyBee F405 Wing');
    expect(profile.name).toBe('SpeedyBee F405 Wing');
  });

  it('returns UNKNOWN_BOARD for an unknown name', () => {
    const profile = getBoardProfileByName('NonexistentBoard');
    expect(profile).toBe(UNKNOWN_BOARD);
  });
});
