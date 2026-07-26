/**
 * @module use-throttled-elapsed
 * @description Samples simulation elapsed time at ~10Hz for components that don't need 60fps updates.
 * Syncs immediately when not playing (scrubber/step).
 * @license GPL-3.0-only
 */

import { useState, useEffect } from "react";
import { useSimulationStore } from "@/stores/simulation-store";

const THROTTLE_MS = 100;

export function useThrottledElapsed(): number {
  const [throttled, setThrottled] = useState(() => useSimulationStore.getState().elapsed);
  const playbackState = useSimulationStore((s) => s.playbackState);

  useEffect(() => {
    if (playbackState !== "playing") {
      // When not playing, sync immediately on elapsed changes only
      let prevElapsed = useSimulationStore.getState().elapsed;
      return useSimulationStore.subscribe((state) => {
        if (state.elapsed !== prevElapsed) {
          prevElapsed = state.elapsed;
          setThrottled(state.elapsed);
        }
      });
    }

    // When playing, sample at ~10Hz
    const id = setInterval(() => {
      setThrottled(useSimulationStore.getState().elapsed);
    }, THROTTLE_MS);
    return () => clearInterval(id);
  }, [playbackState]);

  return throttled;
}
