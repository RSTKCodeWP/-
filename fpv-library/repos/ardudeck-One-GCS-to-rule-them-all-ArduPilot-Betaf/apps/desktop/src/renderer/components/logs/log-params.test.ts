import { describe, it, expect } from 'vitest';
import { extractLogParams, isNonDefault, fmtParamValue } from './log-params';

function parm(timeUs: number, name: string, value: number, def?: number) {
  const fields: Record<string, number | string> = { Name: name, Value: value };
  if (def !== undefined) fields['Default'] = def;
  return { type: 'PARM', timeUs, fields };
}

describe('extractLogParams', () => {
  it('captures first/last values and in-flight changes', () => {
    const params = extractLogParams({
      messages: {
        PARM: [
          parm(1_000_000, 'ATC_RAT_RLL_P', 0.135),
          parm(1_000_000, 'FLTMODE1', 5),
          parm(60_000_000, 'ATC_RAT_RLL_P', 0.15), // changed mid-flight
          parm(120_000_000, 'ATC_RAT_RLL_P', 0.16), // and again
        ],
      },
    });
    const rll = params.find((p) => p.name === 'ATC_RAT_RLL_P')!;
    expect(rll.first).toBeCloseTo(0.135);
    expect(rll.last).toBeCloseTo(0.16);
    expect(rll.changes).toHaveLength(2);
    expect(rll.changes[0]!.timeS).toBe(60);
    expect(rll.changes[1]!.value).toBeCloseTo(0.16);

    const flt = params.find((p) => p.name === 'FLTMODE1')!;
    expect(flt.changes).toHaveLength(0);
  });

  it('ignores re-logs of the same value', () => {
    const params = extractLogParams({
      messages: { PARM: [parm(1, 'X', 5), parm(2, 'X', 5), parm(3, 'X', 5)] },
    });
    expect(params[0]!.changes).toHaveLength(0);
  });

  it('sorts by name and records defaults when present', () => {
    const params = extractLogParams({
      messages: { PARM: [parm(1, 'ZZZ', 1, 1), parm(1, 'AAA', 2, 0)] },
    });
    expect(params.map((p) => p.name)).toEqual(['AAA', 'ZZZ']);
    expect(params[0]!.default).toBe(0);
  });
});

describe('isNonDefault', () => {
  it('flags values that differ from the logged default', () => {
    expect(isNonDefault({ name: 'A', first: 2, last: 2, default: 0, changes: [] })).toBe(true);
    expect(isNonDefault({ name: 'A', first: 0, last: 0, default: 0, changes: [] })).toBe(false);
  });

  it('never flags when the log has no defaults', () => {
    expect(isNonDefault({ name: 'A', first: 2, last: 2, changes: [] })).toBe(false);
  });

  it('tolerates float32 round-trip noise', () => {
    expect(isNonDefault({ name: 'A', first: 0.1, last: 0.1 + 1e-9, default: 0.1, changes: [] })).toBe(false);
  });
});

describe('fmtParamValue', () => {
  it('prints integers plainly and trims float noise', () => {
    expect(fmtParamValue(5)).toBe('5');
    expect(fmtParamValue(0.15000000596046448)).toBe('0.15'); // float32 0.15
  });
});
