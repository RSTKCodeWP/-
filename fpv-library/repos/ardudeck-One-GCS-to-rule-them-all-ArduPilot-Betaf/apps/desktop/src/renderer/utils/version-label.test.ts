import { describe, it, expect } from 'vitest';
import { betaLabel } from './version-label';

describe('betaLabel', () => {
  it('renders 0.x as a Beta milestone (0.<minor>.<patch> -> Beta <minor>[.<patch>])', () => {
    expect(betaLabel('0.1.0')).toBe('Beta 1');
    expect(betaLabel('0.1.2')).toBe('Beta 1.2');
    expect(betaLabel('0.2.1')).toBe('Beta 2.1');
  });

  it('drops the patch when it is zero', () => {
    expect(betaLabel('0.3.0')).toBe('Beta 3');
  });

  it('graduates out of beta at 1.0.0+ and trims a .0 patch', () => {
    expect(betaLabel('1.0.0')).toBe('1.0');
    expect(betaLabel('1.2.0')).toBe('1.2');
    expect(betaLabel('1.2.3')).toBe('1.2.3');
  });

  it('ignores any prerelease suffix', () => {
    expect(betaLabel('0.1.0-beta.1')).toBe('Beta 1');
  });

  it('returns the input unchanged when it is not a parseable version', () => {
    expect(betaLabel('nightly')).toBe('nightly');
  });
});
