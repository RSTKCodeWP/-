/**
 * @module use-sim-completion
 * @description Records simulation history when playback completes
 * (elapsed reaches totalDuration and clock auto-pauses).
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import type { Waypoint } from "@/lib/types";
import { isAtEnd } from "@/lib/sim-clock";
import { useSimulationStore } from "@/stores/simulation-store";
import { useSimHistoryStore } from "@/stores/simulation-history-store";
import { usePlanLibraryStore } from "@/stores/plan-library-store";

/** Record a history entry when simulation playback completes naturally. */
export function useSimCompletion(waypoints: Waypoint[]): void {
  const playbackState = useSimulationStore((s) => s.playbackState);
  const completionRecorded = useRef(false);

  useEffect(() => {
    const { elapsed, totalDuration } = useSimulationStore.getState();

    // Reset flag when playback starts
    if (playbackState === "playing") {
      completionRecorded.current = false;
    }

    // Record when playback stops at the end (natural completion). A manual stop
    // rewinds elapsed to 0, so the end-of-timeline check never false-triggers.
    // The stored elapsed is quantized just below totalDuration, so isAtEnd()
    // (epsilon-tolerant) is used instead of a strict >= comparison.
    if (
      playbackState === "stopped" &&
      isAtEnd(elapsed, totalDuration) &&
      !completionRecorded.current
    ) {
      completionRecorded.current = true;
      const lib = usePlanLibraryStore.getState();
      const activePlan = lib.plans.find((p) => p.id === lib.activePlanId);
      useSimHistoryStore.getState().addEntry({
        planId: lib.activePlanId || "unknown",
        planName: activePlan?.name || "Untitled Plan",
        timestamp: Date.now(),
        duration: totalDuration,
        waypointCount: waypoints.length,
      });
    }
  }, [playbackState, waypoints.length]);
}
