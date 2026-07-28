import { describe, it, expect, beforeEach } from 'vitest';
import { useParameterStore } from './parameter-store';
import type { ParamValuePayload } from '../../shared/parameter-types';

const REAL32 = 9;
// 0.95 is not exactly representable in float32. The FC stores the nearest
// float32 and reports it back as this float64 value. The store must not let
// that IEEE noise leak into the displayed value.
const NOISY_095 = Math.fround(0.95); // 0.949999988079071

function payload(overrides: Partial<ParamValuePayload> = {}): ParamValuePayload {
  return {
    paramId: 'MOT_SPIN_MAX',
    paramValue: NOISY_095,
    paramType: REAL32,
    paramCount: 1,
    paramIndex: 0,
    ...overrides,
  };
}

describe('parameter-store float32 ingestion', () => {
  beforeEach(() => {
    useParameterStore.setState({ parameters: new Map(), paramCount: 0 });
  });

  it('updateParameter (PARAM_VALUE readback) strips float32 noise from value', () => {
    useParameterStore.getState().updateParameter(payload());
    const p = useParameterStore.getState().parameters.get('MOT_SPIN_MAX');
    expect(p?.value).toBe(0.95);
  });

  it('bulkLoadParameters (FTP fast path) strips float32 noise from value', () => {
    useParameterStore.getState().bulkLoadParameters([payload()]);
    const p = useParameterStore.getState().parameters.get('MOT_SPIN_MAX');
    expect(p?.value).toBe(0.95);
  });

  it('leaves integer (non-REAL32) params exactly as received', () => {
    useParameterStore
      .getState()
      .updateParameter(payload({ paramId: 'FRAME_CLASS', paramValue: 1, paramType: 2 }));
    const p = useParameterStore.getState().parameters.get('FRAME_CLASS');
    expect(p?.value).toBe(1);
  });
});
