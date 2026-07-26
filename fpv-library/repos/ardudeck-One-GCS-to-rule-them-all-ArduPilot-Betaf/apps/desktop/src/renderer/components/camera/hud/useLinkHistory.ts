/**
 * Rolling history (0..1) of the radio link quality for the HUD link sparkline.
 * Samples the live RC RSSI (the real signal we have over MAVLink/MSP) on an
 * interval into a fixed ring, so the graph reflects actual link state.
 */

import { useEffect, useRef, useState } from 'react';
import { useTelemetryStore } from '../../../stores/telemetry-store';

const SAMPLES = 60;
const PERIOD_MS = 500;

export function useLinkHistory(enabled: boolean): number[] {
  const [history, setHistory] = useState<number[]>([]);
  const ring = useRef<number[]>([]);

  useEffect(() => {
    if (!enabled) return;
    const tick = () => {
      const raw = useTelemetryStore.getState().rcChannels.rssi;
      const norm = !raw || raw >= 255 ? 0 : Math.min(1, raw <= 100 ? raw / 100 : raw / 254);
      const next = [...ring.current, norm].slice(-SAMPLES);
      ring.current = next;
      setHistory(next);
    };
    tick();
    const id = setInterval(tick, PERIOD_MS);
    return () => clearInterval(id);
  }, [enabled]);

  return history;
}
