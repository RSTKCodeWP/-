import { describe, it, expect } from 'vitest';
import { fftInPlace, estimateSampleRate, resampleUniform, computeSpectrum, peakIndex } from './log-fft';

function sine(n: number, rateHz: number, freqHz: number, amp: number): Float64Array {
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = amp * Math.sin((2 * Math.PI * freqHz * i) / rateHz);
  return out;
}

describe('fftInPlace', () => {
  it('rejects non-power-of-two lengths', () => {
    expect(() => fftInPlace(new Float64Array(3), new Float64Array(3))).toThrow();
  });

  it('transforms an impulse to a flat spectrum', () => {
    const re = new Float64Array(8);
    const im = new Float64Array(8);
    re[0] = 1;
    fftInPlace(re, im);
    for (let i = 0; i < 8; i++) {
      expect(Math.hypot(re[i]!, im[i]!)).toBeCloseTo(1, 10);
    }
  });
});

describe('estimateSampleRate', () => {
  it('recovers the rate from jittered timestamps', () => {
    const times = Array.from({ length: 400 }, (_, i) => i / 400 + (i % 3) * 1e-5);
    const rate = estimateSampleRate(times)!;
    expect(rate).toBeGreaterThan(380);
    expect(rate).toBeLessThan(420);
  });

  it('returns null on degenerate input', () => {
    expect(estimateSampleRate([1, 1, 1])).toBeNull();
    expect(estimateSampleRate([1])).toBeNull();
  });
});

describe('resampleUniform', () => {
  it('linearly interpolates onto a uniform grid', () => {
    const out = resampleUniform([0, 0.1, 0.2], [0, 10, 20], 20);
    // Grid: 0, 0.05, 0.1, 0.15, 0.2
    expect(out.length).toBe(5);
    expect(out[0]).toBeCloseTo(0);
    expect(out[1]).toBeCloseTo(5);
    expect(out[2]).toBeCloseTo(10);
    expect(out[3]).toBeCloseTo(15);
    expect(out[4]).toBeCloseTo(20);
  });
});

describe('computeSpectrum', () => {
  it('finds a pure sine at the right frequency with calibrated amplitude', () => {
    // 50 Hz sine, amp 3, sampled at 400 Hz: bin 512 of a 4096-seg is exactly 50 Hz.
    const spec = computeSpectrum(sine(4096, 400, 50, 3), 400)!;
    const pk = peakIndex(spec);
    expect(spec.freqHz[pk]).toBeCloseTo(50, 1);
    expect(spec.amplitude[pk]!).toBeGreaterThan(2.8);
    expect(spec.amplitude[pk]!).toBeLessThan(3.2);
  });

  it('resolves two tones with Welch averaging across segments', () => {
    const n = 4096;
    const a = sine(n, 400, 25, 2); // bin-aligned for segLen 1024 at 400 Hz
    const b = sine(n, 400, 125, 0.5);
    const mixed = new Float64Array(n);
    for (let i = 0; i < n; i++) mixed[i] = a[i]! + b[i]! + 7; // +7 DC offset must vanish
    const spec = computeSpectrum(mixed, 400, { maxSegLen: 1024 })!;
    expect(spec.segLen).toBe(1024);
    expect(spec.segments).toBeGreaterThan(1);

    const at = (hz: number) => spec.amplitude[Math.round((hz / 400) * spec.segLen)]!;
    expect(at(25)).toBeGreaterThan(1.8);
    expect(at(125)).toBeGreaterThan(0.4);
    expect(at(125)).toBeLessThan(0.6);
    // DC removed per segment
    expect(spec.amplitude[0]!).toBeLessThan(0.1);
  });

  it('returns null when there is not enough data', () => {
    expect(computeSpectrum(new Float64Array(32), 400)).toBeNull();
  });
});
