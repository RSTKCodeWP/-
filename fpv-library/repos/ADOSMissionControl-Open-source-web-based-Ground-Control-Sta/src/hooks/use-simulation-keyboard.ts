/**
 * @module use-simulation-keyboard
 * @description Keyboard shortcuts for simulation playback controls.
 * Space = play/pause, Left/Right = step, [ ] = speed, Home = reset, End = skip to end.
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useSimulationStore } from "@/stores/simulation-store";
import { usePlanLibraryStore } from "@/stores/plan-library-store";
import { PLAYBACK_SPEEDS } from "@/lib/sim-clock";

const SPEED_OPTIONS: readonly number[] = PLAYBACK_SPEEDS;

export function useSimulationKeyboard(active: boolean) {
  useEffect(() => {
    if (!active) return;

    function handleKey(e: KeyboardEvent) {
      // Don't capture when typing in inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      const store = useSimulationStore.getState();

      switch (e.key) {
        case " ":
          e.preventDefault();
          if (store.playbackState === "playing") {
            store.pause();
          } else {
            store.play();
          }
          break;
        case "ArrowLeft":
          e.preventDefault();
          store.stepBack();
          break;
        case "ArrowRight":
          e.preventDefault();
          store.stepForward();
          break;
        case "[": {
          const idx = SPEED_OPTIONS.indexOf(store.playbackSpeed);
          if (idx > 0) store.setSpeed(SPEED_OPTIONS[idx - 1]);
          break;
        }
        case "]": {
          const idx = SPEED_OPTIONS.indexOf(store.playbackSpeed);
          if (idx < SPEED_OPTIONS.length - 1) store.setSpeed(SPEED_OPTIONS[idx + 1]);
          break;
        }
        case "Home":
          e.preventDefault();
          store.resetPlayback();
          break;
        case "End":
          e.preventDefault();
          store.seek(store.totalDuration);
          break;
        case "t":
          store.setCameraMode("topdown");
          break;
        case "f":
          store.setCameraMode("follow");
          break;
        case "o":
          store.setCameraMode("orbit");
          break;
        case "x":
          store.setCameraMode("free");
          break;
        case "l": {
          usePlanLibraryStore.getState().toggleLibrary();
          break;
        }
        case "Escape":
          e.preventDefault();
          store.stop();
          break;
        case "r":
          // Reset PLAYBACK only — stop and rewind to the start, preserving the
          // computed duration, camera mode, and speed. A full reset() zeroes
          // totalDuration and bricks playback; resetting the view is separate.
          e.preventDefault();
          store.resetPlayback();
          break;
        default: {
          // Number keys 1-9: seek to proportional position in the flight
          const num = parseInt(e.key);
          if (num >= 1 && num <= 9) {
            const { totalDuration } = store;
            if (totalDuration > 0) {
              store.seek((num / 10) * totalDuration);
            }
          }
          break;
        }
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [active]);
}
