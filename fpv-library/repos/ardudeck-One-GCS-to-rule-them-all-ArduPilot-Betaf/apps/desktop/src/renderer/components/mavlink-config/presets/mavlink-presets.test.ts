import { describe, it, expect, vi } from 'vitest';

// Mock lucide-react since it's a renderer dependency not available in Node tests
vi.mock('lucide-react', () => ({
  Egg: 'Egg',
  Drama: 'Drama',
  Zap: 'Zap',
  Film: 'Film',
}));

import { PID_PRESETS } from './mavlink-presets';

// ---------------------------------------------------------------------------
// PID Preset accel values
// ---------------------------------------------------------------------------

describe('PID Preset acceleration limits', () => {
  it('all presets should define accel values', () => {
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      expect(preset.accel, `preset "${key}" should have accel`).toBeDefined();
      expect(preset.accel!.roll, `preset "${key}" roll accel`).toBeGreaterThan(0);
      expect(preset.accel!.pitch, `preset "${key}" pitch accel`).toBeGreaterThan(0);
      expect(preset.accel!.yaw, `preset "${key}" yaw accel`).toBeGreaterThan(0);
    }
  });

  it('beginner preset should have lowest accel limits', () => {
    const beginner = PID_PRESETS['beginner']!;
    const racing = PID_PRESETS['racing']!;
    expect(beginner.accel!.roll).toBeLessThan(racing.accel!.roll);
    expect(beginner.accel!.pitch).toBeLessThan(racing.accel!.pitch);
    expect(beginner.accel!.yaw).toBeLessThan(racing.accel!.yaw);
  });

  it('racing preset should have highest accel limits', () => {
    const racing = PID_PRESETS['racing']!;
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      if (key === 'racing') continue;
      expect(racing.accel!.roll).toBeGreaterThanOrEqual(preset.accel!.roll);
      expect(racing.accel!.pitch).toBeGreaterThanOrEqual(preset.accel!.pitch);
      expect(racing.accel!.yaw).toBeGreaterThanOrEqual(preset.accel!.yaw);
    }
  });

  it('cinematic preset should have lower accel than freestyle', () => {
    const cinematic = PID_PRESETS['cinematic']!;
    const freestyle = PID_PRESETS['freestyle']!;
    expect(cinematic.accel!.roll).toBeLessThan(freestyle.accel!.roll);
    expect(cinematic.accel!.pitch).toBeLessThan(freestyle.accel!.pitch);
    expect(cinematic.accel!.yaw).toBeLessThan(freestyle.accel!.yaw);
  });

  it('yaw accel should always be lower than roll/pitch accel', () => {
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      expect(preset.accel!.yaw, `preset "${key}" yaw < roll`).toBeLessThan(preset.accel!.roll);
      expect(preset.accel!.yaw, `preset "${key}" yaw < pitch`).toBeLessThan(preset.accel!.pitch);
    }
  });

  it('specific preset accel values match expected constants', () => {
    expect(PID_PRESETS['beginner']!.accel).toEqual({ roll: 80000, pitch: 80000, yaw: 20000 });
    expect(PID_PRESETS['freestyle']!.accel).toEqual({ roll: 110000, pitch: 110000, yaw: 27000 });
    expect(PID_PRESETS['racing']!.accel).toEqual({ roll: 160000, pitch: 160000, yaw: 40000 });
    expect(PID_PRESETS['cinematic']!.accel).toEqual({ roll: 55000, pitch: 55000, yaw: 14000 });
  });
});

// ---------------------------------------------------------------------------
// Preset accel scaling consistency
// ---------------------------------------------------------------------------

describe('PID Preset accel scaling relationships', () => {
  it('roll and pitch accel should be symmetric for all presets', () => {
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      expect(preset.accel!.roll, `preset "${key}" roll == pitch`).toBe(preset.accel!.pitch);
    }
  });

  it('accel values should follow a reasonable ordering across presets', () => {
    const order = ['cinematic', 'beginner', 'freestyle', 'racing'];
    for (let idx = 1; idx < order.length; idx++) {
      const prev = PID_PRESETS[order[idx - 1]!]!;
      const curr = PID_PRESETS[order[idx]!]!;
      expect(curr.accel!.roll, `${order[idx]} roll > ${order[idx - 1]} roll`)
        .toBeGreaterThan(prev.accel!.roll);
      expect(curr.accel!.yaw, `${order[idx]} yaw > ${order[idx - 1]} yaw`)
        .toBeGreaterThan(prev.accel!.yaw);
    }
  });

  it('yaw-to-roll ratio should be roughly consistent across presets', () => {
    // Yaw accel is typically ~25% of roll accel for all presets
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      const ratio = preset.accel!.yaw / preset.accel!.roll;
      expect(ratio, `preset "${key}" yaw/roll ratio should be 15-30%`).toBeGreaterThanOrEqual(0.15);
      expect(ratio, `preset "${key}" yaw/roll ratio should be 15-30%`).toBeLessThanOrEqual(0.30);
    }
  });

  it('every preset has both PID values and accel values', () => {
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      // PID values
      expect(preset.values, `preset "${key}" should have PID values`).toBeDefined();
      expect(preset.values.roll.p, `preset "${key}" roll P`).toBeGreaterThan(0);
      // Accel values
      expect(preset.accel, `preset "${key}" should have accel`).toBeDefined();
      expect(preset.accel!.roll, `preset "${key}" accel roll`).toBeGreaterThan(0);
    }
  });

  it('accel values are in cdeg/s² range (not deg/s²)', () => {
    // Values should be in the thousands-to-hundred-thousands range (cdeg/s²)
    // If someone accidentally used deg/s², values would be < 2000
    for (const [key, preset] of Object.entries(PID_PRESETS)) {
      expect(preset.accel!.roll, `preset "${key}" roll in cdeg/s²`).toBeGreaterThan(10000);
      expect(preset.accel!.pitch, `preset "${key}" pitch in cdeg/s²`).toBeGreaterThan(10000);
      expect(preset.accel!.yaw, `preset "${key}" yaw in cdeg/s²`).toBeGreaterThan(10000);
    }
  });
});
