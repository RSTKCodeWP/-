/**
 * FFT analysis for PID tuning.
 *
 * Radix-2 Cooley-Tukey FFT with Hanning window, power spectral density,
 * and peak detection with frequency zone classification.
 *
 * @license GPL-3.0-only
 */

import type { TimeSample, FFTAxisResult, FFTBin, FFTPeak } from "@/lib/analysis/types";

// ---------------------------------------------------------------------------
// Window function
// ---------------------------------------------------------------------------

/** Apply a Hanning window to the sample array (in-place). */
function hanningWindow(data: Float64Array): void {
  const n = data.length;
  for (let i = 0; i < n; i++) {
    const w = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1)));
    data[i] *= w;
  }
}

// ---------------------------------------------------------------------------
// Radix-2 Cooley-Tukey FFT (in-place, iterative)
// ---------------------------------------------------------------------------

/**
 * In-place iterative radix-2 FFT.
 * `re` and `im` are the real and imaginary parts, both length N (power of 2).
 */
function fftInPlace(re: Float64Array, im: Float64Array): void {
  const n = re.length;

  // Bit-reversal permutation
  let j = 0;
  for (let i = 0; i < n - 1; i++) {
    if (i < j) {
      let tmp = re[i];
      re[i] = re[j];
      re[j] = tmp;
      tmp = im[i];
      im[i] = im[j];
      im[j] = tmp;
    }
    let m = n >> 1;
    while (m >= 1 && j >= m) {
      j -= m;
      m >>= 1;
    }
    j += m;
  }

  // Butterfly stages
  for (let size = 2; size <= n; size <<= 1) {
    const halfSize = size >> 1;
    const angleStep = (-2 * Math.PI) / size;
    for (let i = 0; i < n; i += size) {
      for (let k = 0; k < halfSize; k++) {
        const angle = angleStep * k;
        const twRe = Math.cos(angle);
        const twIm = Math.sin(angle);

        const evenIdx = i + k;
        const oddIdx = i + k + halfSize;

        const tRe = twRe * re[oddIdx] - twIm * im[oddIdx];
        const tIm = twRe * im[oddIdx] + twIm * re[oddIdx];

        re[oddIdx] = re[evenIdx] - tRe;
        im[oddIdx] = im[evenIdx] - tIm;
        re[evenIdx] += tRe;
        im[evenIdx] += tIm;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Round up to the next power of 2. */
function nextPow2(n: number): number {
  let p = 1;
  while (p < n) p <<= 1;
  return p;
}

/** Classify a frequency into a noise zone. */
function classifyFrequency(hz: number): FFTPeak["zone"] {
  if (hz >= 20 && hz <= 100) return "propwash";
  if (hz > 100 && hz <= 200) return "structural";
  if (hz > 200 && hz <= 400) return "motor";
  return "unknown";
}

/** Compute median of a Float64Array. */
function median(arr: Float64Array): number {
  const sorted = Float64Array.from(arr).sort();
  const mid = sorted.length >> 1;
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compute FFT on a set of time-domain samples.
 *
 * @param samples  Time-value pairs (value = gyro rate in deg/s or similar)
 * @param sampleRate  Sample rate in Hz
 * @param axis  Which axis these samples represent
 * @returns FFT result with spectrum, peaks, and noise floor
 */
export function computeFFT(
  samples: TimeSample[],
  sampleRate: number,
  axis: "roll" | "pitch" | "yaw",
): FFTAxisResult {
  if (samples.length < 2) {
    return { axis, spectrum: [], sampleRate, peaks: [], noiseFloorDb: -120 };
  }

  const n = nextPow2(samples.length);

  // Prepare windowed real array, zero-padded
  const re = new Float64Array(n);
  const im = new Float64Array(n);
  for (let i = 0; i < samples.length; i++) {
    re[i] = samples[i].value;
  }
  hanningWindow(re);

  // Run FFT
  fftInPlace(re, im);

  // Compute power spectral density (magnitude in dB)
  // Only positive frequencies (0 to N/2)
  const halfN = n >> 1;
  const freqResolution = sampleRate / n;
  const spectrum: FFTBin[] = new Array(halfN);
  const magnitudes = new Float64Array(halfN);

  for (let i = 0; i < halfN; i++) {
    const mag = Math.sqrt(re[i] * re[i] + im[i] * im[i]) / n;
    const magDb = mag > 0 ? 20 * Math.log10(mag) : -120;
    spectrum[i] = {
      frequency: i * freqResolution,
      magnitude: magDb,
    };
    magnitudes[i] = magDb;
  }

  // Noise floor = median magnitude
  const noiseFloorDb = median(magnitudes);

  // Peak detection: find local maxima above noise floor + 6 dB
  const threshold = noiseFloorDb + 6;
  const peaks: FFTPeak[] = [];

  for (let i = 2; i < halfN - 2; i++) {
    const mag = magnitudes[i];
    if (
      mag > threshold &&
      mag > magnitudes[i - 1] &&
      mag > magnitudes[i + 1] &&
      mag > magnitudes[i - 2] &&
      mag > magnitudes[i + 2]
    ) {
      peaks.push({
        frequency: i * freqResolution,
        magnitudeDb: mag,
        zone: classifyFrequency(i * freqResolution),
      });
    }
  }

  // Sort peaks by magnitude descending
  peaks.sort((a, b) => b.magnitudeDb - a.magnitudeDb);

  return {
    axis,
    spectrum,
    sampleRate,
    peaks,
    noiseFloorDb,
  };
}
