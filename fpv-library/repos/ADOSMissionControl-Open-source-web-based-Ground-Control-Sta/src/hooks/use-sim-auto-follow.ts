/**
 * @module use-sim-auto-follow
 * @description Optional auto-follow. When the "auto-follow on play" preference
 * is enabled, the simulation camera switches to follow (chase-cam) when
 * playback starts and restores the prior mode when playback stops. Follow
 * otherwise stays an explicit user choice via the camera cluster.
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import { useSimulationStore, type CameraMode } from "@/stores/simulation-store";
import { useSettingsStore } from "@/stores/settings-store";

export function useSimAutoFollow(): void {
  const autoFollowOnPlay = useSettingsStore((s) => s.autoFollowOnPlay);
  const playbackState = useSimulationStore((s) => s.playbackState);
  // The mode to restore on stop, or null when we are not driving the camera.
  const prevModeRef = useRef<CameraMode | null>(null);

  useEffect(() => {
    if (!autoFollowOnPlay) {
      // If we engaged follow this run and are still in it, restore the prior
      // mode so turning the preference off is fully effective mid-play.
      const sim = useSimulationStore.getState();
      if (prevModeRef.current !== null && sim.cameraMode === "follow") {
        sim.setCameraMode(prevModeRef.current);
      }
      prevModeRef.current = null;
      return;
    }
    const { cameraMode, setCameraMode } = useSimulationStore.getState();
    if (playbackState === "playing") {
      // Engage follow once at the start of a run, remembering where to return.
      if (prevModeRef.current === null && cameraMode !== "follow") {
        prevModeRef.current = cameraMode;
        setCameraMode("follow");
      }
    } else if (playbackState === "stopped" && prevModeRef.current !== null) {
      // Restore only if we are still in control — if the user manually switched
      // away from follow mid-run, respect their choice and don't override it.
      if (useSimulationStore.getState().cameraMode === "follow") {
        setCameraMode(prevModeRef.current);
      }
      prevModeRef.current = null;
    }
  }, [autoFollowOnPlay, playbackState]);
}
