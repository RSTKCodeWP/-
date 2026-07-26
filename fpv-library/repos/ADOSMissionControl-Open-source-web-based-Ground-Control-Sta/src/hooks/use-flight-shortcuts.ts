/**
 * @module use-flight-shortcuts
 * @description Keyboard shortcuts for flight actions (Shift+key).
 * ARM/DISARM, RTH, Land, Takeoff, Pause/Hold/Resume, Abort.
 * Kill has no shortcut (too dangerous, requires 2-step click).
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useDroneStore } from "@/stores/drone-store";
import { useDroneManager } from "@/stores/drone-manager";
import { useToast } from "@/components/ui/toast";

interface UseFlightShortcutsParams {
  enabled: boolean;
  onArmConfirm: () => void;
  onDisarmConfirm: () => void;
  onRthConfirm: () => void;
  onTakeoffConfirm: () => void;
  onLandConfirm: () => void;
  onAbortConfirm: () => void;
  takeoffAlt: string;
}

export function useFlightShortcuts({
  enabled,
  onArmConfirm,
  onDisarmConfirm,
  onRthConfirm,
  onTakeoffConfirm,
  onLandConfirm,
  onAbortConfirm,
  takeoffAlt,
}: UseFlightShortcutsParams) {
  const { toast } = useToast();

  useEffect(() => {
    if (!enabled) return;

    function handleKey(e: KeyboardEvent) {
      // Require Shift held, reject if Ctrl/Meta/Alt also held
      if (!e.shiftKey || e.ctrlKey || e.metaKey || e.altKey) return;

      // Don't capture when typing in inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      const droneState = useDroneStore.getState();
      const isArmed = droneState.armState === "armed";

      switch (e.key) {
        case "A": {
          // ARM / DISARM toggle: open the same confirmation flow as the UI.
          e.preventDefault();
          if (isArmed) onDisarmConfirm();
          else onArmConfirm();
          break;
        }
        case "R": {
          // Return to Home (opens confirmation dialog)
          e.preventDefault();
          onRthConfirm();
          break;
        }
        case "L": {
          // Land: open confirmation flow.
          e.preventDefault();
          onLandConfirm();
          break;
        }
        case "T": {
          // Takeoff
          e.preventDefault();
          const alt = parseFloat(takeoffAlt);
          if (isNaN(alt) || alt <= 0) {
            toast("Invalid takeoff altitude", "error");
            return;
          }
          void alt;
          onTakeoffConfirm();
          break;
        }
        case "P": {
          // Pause / Hold / Resume (context-dependent)
          e.preventDefault();
          const mode = droneState.flightMode;
          const prevMode = droneState.previousMode;
          const protocol = useDroneManager.getState().getSelectedProtocol();

          if (mode === "AUTO") {
            if (protocol) protocol.pauseMission();
            else droneState.setFlightMode("LOITER");
            toast("Mission paused", "info");
          } else if (mode === "LOITER" && prevMode === "AUTO") {
            if (protocol) protocol.resumeMission();
            else droneState.setFlightMode("AUTO");
            toast("Mission resumed", "success");
          } else {
            if (protocol) protocol.setFlightMode("LOITER");
            else droneState.setFlightMode("LOITER");
            toast("Hold position", "info");
          }
          break;
        }
        case "X": {
          // Abort (opens confirmation dialog)
          e.preventDefault();
          onAbortConfirm();
          break;
        }
        default:
          break;
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [
    enabled,
    onArmConfirm,
    onDisarmConfirm,
    onRthConfirm,
    onTakeoffConfirm,
    onLandConfirm,
    onAbortConfirm,
    takeoffAlt,
    toast,
  ]);
}
