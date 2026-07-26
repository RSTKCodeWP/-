/**
 * Hook for reading/writing ArduPilot SIM_* parameters with smooth UX.
 *
 * Maintains local state so sliders respond instantly, while debouncing
 * the actual PARAM_SET writes to avoid flooding the FC.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useParameterStore } from '../stores/parameter-store';

export function useSimParam(paramId: string, defaultValue = 0) {
  const storeValue = useParameterStore((s) => s.parameters.get(paramId)?.value);
  const setParameter = useParameterStore((s) => s.setParameter);
  const [local, setLocal] = useState<number | undefined>(undefined);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const value = local ?? storeValue ?? defaultValue;
  const available = storeValue !== undefined;

  const setValue = useCallback(
    (v: number) => {
      setLocal(v);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setParameter(paramId, v);
      }, 300);
    },
    [paramId, setParameter],
  );

  // Flush: send immediately without debounce (for toggles)
  const setValueImmediate = useCallback(
    (v: number) => {
      setLocal(v);
      clearTimeout(timerRef.current);
      setParameter(paramId, v);
    },
    [paramId, setParameter],
  );

  // Reset local override when param ID changes
  useEffect(() => {
    setLocal(undefined);
  }, [paramId]);

  // Cleanup debounce timer
  useEffect(() => () => clearTimeout(timerRef.current), []);

  return { value, setValue, setValueImmediate, available } as const;
}

/**
 * Resolves a SIM parameter that may have different names across ArduPilot versions.
 * Tries each candidate in order, returns the first one found in the parameter store.
 */
export function useResolvedSimParam(candidates: string[], defaultValue = 0) {
  const parameters = useParameterStore((s) => s.parameters);

  const resolvedId = candidates.find((id) => parameters.has(id)) ?? candidates[0]!;

  return { ...useSimParam(resolvedId, defaultValue), paramId: resolvedId };
}
