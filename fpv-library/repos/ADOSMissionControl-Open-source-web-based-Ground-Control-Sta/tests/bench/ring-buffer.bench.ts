import { describe, bench } from 'vitest';
import { RingBuffer } from '@/lib/ring-buffer';

describe('RingBuffer Benchmarks', () => {
  bench('push 18000 items (30min telemetry at 10Hz)', () => {
    const rb = new RingBuffer<number>(18000);
    for (let i = 0; i < 18000; i++) {
      rb.push(i);
    }
  });

  bench('push + toArray 1000 items', () => {
    const rb = new RingBuffer<number>(1000);
    for (let i = 0; i < 1000; i++) {
      rb.push(i);
    }
    rb.toArray();
  });

  bench('get() random access 1000 times', () => {
    const rb = new RingBuffer<number>(1000);
    for (let i = 0; i < 1000; i++) rb.push(i);
    for (let i = 0; i < 1000; i++) {
      rb.get(Math.floor(Math.random() * 1000));
    }
  });

  bench('last(100) on full buffer', () => {
    const rb = new RingBuffer<number>(18000);
    for (let i = 0; i < 18000; i++) rb.push(i);
    rb.last(100);
  });
});
