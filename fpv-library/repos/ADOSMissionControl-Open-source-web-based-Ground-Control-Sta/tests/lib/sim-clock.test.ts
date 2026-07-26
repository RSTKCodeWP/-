import { describe, it, expect } from 'vitest';
import {
  STEP_SECONDS,
  PLAYBACK_SPEEDS,
  quantizeElapsed,
  clampElapsed,
  stepForwardElapsed,
  stepBackElapsed,
  isAtEnd,
  resumeElapsedForDuration,
} from '@/lib/sim-clock';

describe('sim-clock', () => {
  it('exposes a one-second step', () => {
    expect(STEP_SECONDS).toBe(1);
  });

  it('exposes a single ordered speed list', () => {
    expect([...PLAYBACK_SPEEDS]).toEqual([0.25, 0.5, 1, 2, 4]);
  });

  it('quantizeElapsed rounds to milliseconds', () => {
    expect(quantizeElapsed(1.23456)).toBe(1.235);
    expect(quantizeElapsed(0)).toBe(0);
  });

  describe('clampElapsed', () => {
    it('clamps into [0, totalDuration]', () => {
      expect(clampElapsed(50, 100)).toBe(50);
      expect(clampElapsed(150, 100)).toBe(100);
      expect(clampElapsed(-10, 100)).toBe(0);
    });

    it('treats a zero/negative duration as zero-length', () => {
      expect(clampElapsed(50, 0)).toBe(0);
      expect(clampElapsed(50, -5)).toBe(0);
    });
  });

  describe('stepForward / stepBack', () => {
    it('steps by one second and clamps at the ends', () => {
      expect(stepForwardElapsed(10, 100)).toBe(11);
      expect(stepForwardElapsed(100, 100)).toBe(100);
      expect(stepBackElapsed(10, 100)).toBe(9);
      expect(stepBackElapsed(0, 100)).toBe(0);
    });
  });

  describe('isAtEnd', () => {
    it('is true at or just shy of the end (epsilon-tolerant)', () => {
      expect(isAtEnd(100, 100)).toBe(true);
      expect(isAtEnd(99.9995, 100)).toBe(true);
      expect(isAtEnd(99, 100)).toBe(false);
    });

    it('is false for an empty timeline', () => {
      expect(isAtEnd(0, 0)).toBe(false);
    });
  });

  describe('resumeElapsedForDuration', () => {
    it('preserves a non-zero position on a duration change', () => {
      expect(resumeElapsedForDuration(80, 300)).toBe(80);
    });

    it('re-clamps an elapsed past a shorter new duration', () => {
      expect(resumeElapsedForDuration(180, 120)).toBe(120);
    });
  });
});
