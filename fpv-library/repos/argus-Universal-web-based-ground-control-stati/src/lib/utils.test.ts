import { describe, it, expect } from 'vitest';
import { cn } from './utils';

describe('cn (class merge utility)', () => {
  it('merges multiple class strings', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1');
  });

  it('deduplicates conflicting tailwind classes', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible');
  });

  it('handles undefined and null inputs', () => {
    expect(cn('base', undefined, null, 'end')).toBe('base end');
  });

  it('handles empty string', () => {
    expect(cn('')).toBe('');
  });

  it('handles array inputs', () => {
    expect(cn(['px-2', 'py-1'])).toBe('px-2 py-1');
  });

  it('merges complex tailwind patterns', () => {
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('preserves non-conflicting classes', () => {
    expect(cn('font-bold', 'text-sm', 'rounded-md')).toBe('font-bold text-sm rounded-md');
  });
});
