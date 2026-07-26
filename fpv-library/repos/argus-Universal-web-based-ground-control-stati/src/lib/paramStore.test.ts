import { describe, it, expect, beforeEach } from 'vitest';
import {
  paramState,
  handleParamBatch,
  handleParamsComplete,
  handleParamTimeout,
  getParam,
  clearParams,
} from './paramStore.svelte';

beforeEach(() => {
  clearParams();
});

describe('handleParamBatch', () => {
  it('adds params to list', () => {
    handleParamBatch([
      { name: 'ANGLE_MAX', value: 3000, ptype: 9, index: 0, total: 2, received: 1 },
      { name: 'BATT_ARM_VOLT', value: 10.5, ptype: 9, index: 1, total: 2, received: 2 },
    ]);
    expect(paramState.list.length).toBe(2);
    expect(paramState.list[0].name).toBe('ANGLE_MAX');
    expect(paramState.total).toBe(2);
  });

  it('updates existing param by name', () => {
    handleParamBatch([{ name: 'X', value: 1, ptype: 9, index: 0, total: 1, received: 1 }]);
    handleParamBatch([{ name: 'X', value: 2, ptype: 9, index: 0, total: 1, received: 1 }]);
    expect(paramState.list.length).toBe(1);
    expect(paramState.list[0].value).toBe(2);
  });

  it('sets fetching true when incomplete', () => {
    handleParamBatch([{ name: 'A', value: 0, ptype: 9, index: 0, total: 10, received: 1 }]);
    expect(paramState.fetching).toBe(true);
  });
});

describe('handleParamsComplete', () => {
  it('sets fetching false and sorts', () => {
    handleParamBatch([
      { name: 'Z_PARAM', value: 0, ptype: 9, index: 0, total: 2, received: 1 },
      { name: 'A_PARAM', value: 0, ptype: 9, index: 1, total: 2, received: 2 },
    ]);
    handleParamsComplete();
    expect(paramState.fetching).toBe(false);
    expect(paramState.list[0].name).toBe('A_PARAM');
    expect(paramState.list[1].name).toBe('Z_PARAM');
  });
});

describe('handleParamTimeout', () => {
  it('sets fetching false on timeout', () => {
    handleParamBatch([{ name: 'A', value: 0, ptype: 9, index: 0, total: 10, received: 1 }]);
    expect(paramState.fetching).toBe(true);
    handleParamTimeout();
    expect(paramState.fetching).toBe(false);
  });
});

describe('getParam', () => {
  it('returns value by name via O(1) lookup', () => {
    handleParamBatch([{ name: 'TEST', value: 42, ptype: 9, index: 0, total: 1, received: 1 }]);
    expect(getParam('TEST', 0)).toBe(42);
  });

  it('returns fallback for unknown param', () => {
    expect(getParam('NONEXISTENT', -1)).toBe(-1);
  });

  it('works after sort', () => {
    handleParamBatch([
      { name: 'Z_PARAM', value: 10, ptype: 9, index: 0, total: 2, received: 1 },
      { name: 'A_PARAM', value: 20, ptype: 9, index: 1, total: 2, received: 2 },
    ]);
    handleParamsComplete();
    expect(getParam('A_PARAM', 0)).toBe(20);
    expect(getParam('Z_PARAM', 0)).toBe(10);
  });
});

describe('clearParams', () => {
  it('resets all state', () => {
    handleParamBatch([{ name: 'X', value: 1, ptype: 9, index: 0, total: 1, received: 1 }]);
    clearParams();
    expect(paramState.list.length).toBe(0);
    expect(paramState.total).toBe(0);
    expect(paramState.fetching).toBe(false);
  });

  it('clears nameIndex so subsequent batches start fresh', () => {
    handleParamBatch([{ name: 'OLD', value: 1, ptype: 9, index: 0, total: 1, received: 1 }]);
    clearParams();
    handleParamBatch([{ name: 'NEW', value: 2, ptype: 9, index: 0, total: 1, received: 1 }]);
    expect(paramState.list.length).toBe(1);
    expect(paramState.list[0].name).toBe('NEW');
  });
});

describe('param edit round-trip precision', () => {
  const cases = [0, 1, -1, 0.001, 0.123456, 99.9999, 100, 100.5, 3.4028235e38, -3.4028235e38, 1e-7, 16777216, 16777217];

  for (const v of cases) {
    it(`String(${v}) → parseFloat preserves value`, () => {
      const roundTrip = parseFloat(String(v));
      expect(roundTrip).toBe(v);
    });
  }

  it('export line preserves value (tab-separated)', () => {
    const value = 99.9999;
    const line = `PARAM_NAME\t${value}`;
    const parsed = parseFloat(line.split('\t')[1]);
    expect(parsed).toBe(value);
  });
});

describe('handleParamBatch edge cases', () => {
  it('ignores empty batch array', () => {
    handleParamBatch([]);
    expect(paramState.list.length).toBe(0);
    expect(paramState.total).toBe(0);
    expect(paramState.fetching).toBe(false);
  });

  it('sets fetching false when received equals total', () => {
    handleParamBatch([{ name: 'A', value: 1, ptype: 9, index: 0, total: 1, received: 1 }]);
    expect(paramState.fetching).toBe(false);
  });

  it('handles multiple batches accumulating params', () => {
    handleParamBatch([{ name: 'A', value: 1, ptype: 9, index: 0, total: 3, received: 1 }]);
    handleParamBatch([
      { name: 'B', value: 2, ptype: 9, index: 1, total: 3, received: 2 },
      { name: 'C', value: 3, ptype: 9, index: 2, total: 3, received: 3 },
    ]);
    expect(paramState.list.length).toBe(3);
    expect(paramState.received).toBe(3);
    expect(paramState.fetching).toBe(false);
  });
});
