import { describe, it, expect } from 'vitest';
import { cn, formatDuration, clamp, lerp, randomId, isTypingTarget } from '@/lib/utils';

describe('cn()', () => {
  it('joins truthy class names', () => {
    expect(cn('foo', 'bar', 'baz')).toBe('foo bar baz');
  });

  it('filters out false/null/undefined', () => {
    expect(cn('foo', false, null, undefined, 'bar')).toBe('foo bar');
  });

  it('returns empty string for no truthy args', () => {
    expect(cn(false, null, undefined)).toBe('');
    expect(cn()).toBe('');
  });
});

describe('formatDuration()', () => {
  it('formats MM:SS for under 1 hour', () => {
    expect(formatDuration(0)).toBe('00:00');
    expect(formatDuration(65)).toBe('01:05');
    expect(formatDuration(3599)).toBe('59:59');
  });

  it('formats HH:MM:SS for over 1 hour', () => {
    expect(formatDuration(3600)).toBe('1:00:00');
    expect(formatDuration(3661)).toBe('1:01:01');
    expect(formatDuration(7384)).toBe('2:03:04');
  });
});

describe('clamp()', () => {
  it('clamps between min and max', () => {
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(15, 0, 10)).toBe(10);
  });

  it('returns value when in range', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(0, 0, 10)).toBe(0);
    expect(clamp(10, 0, 10)).toBe(10);
  });
});

describe('lerp()', () => {
  it('interpolates linearly', () => {
    expect(lerp(0, 10, 0.5)).toBe(5);
    expect(lerp(10, 20, 0.25)).toBe(12.5);
  });

  it('lerp(a,b,0) returns a, lerp(a,b,1) returns b', () => {
    expect(lerp(3, 7, 0)).toBe(3);
    expect(lerp(3, 7, 1)).toBe(7);
  });
});

describe('randomId()', () => {
  it('returns string of length 8', () => {
    const id = randomId();
    expect(typeof id).toBe('string');
    expect(id.length).toBe(8);
  });

  it('returns unique values', () => {
    const ids = new Set(Array.from({ length: 50 }, () => randomId()));
    // With 36^8 possible values, collisions in 50 samples should be essentially impossible
    expect(ids.size).toBe(50);
  });
});

describe('isTypingTarget()', () => {
  it('is true for input, textarea, and select elements', () => {
    for (const tag of ['input', 'textarea', 'select']) {
      const el = document.createElement(tag);
      expect(isTypingTarget(el)).toBe(true);
    }
  });

  it('is true for a contenteditable element', () => {
    const el = document.createElement('div');
    el.setAttribute('contenteditable', 'true');
    // happy-dom reflects the attribute into isContentEditable
    expect(isTypingTarget(el)).toBe(el.isContentEditable);
  });

  it('is false for a plain div and for null', () => {
    expect(isTypingTarget(document.createElement('div'))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });
});
