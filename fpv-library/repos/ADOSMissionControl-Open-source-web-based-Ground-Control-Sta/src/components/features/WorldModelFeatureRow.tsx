"use client";

/**
 * @module features/WorldModelFeatureRow
 * @description The master-enable control for the World Model (Atlas) first-party
 * feature, one drone. Toggling ON both reveals the World Model + Live World
 * node-detail tabs (via the per-node features store, which gates the surfaces
 * and the readiness poll) AND enables the native capture service on the drone
 * over the LAN. Toggling OFF disables the service and hides the tabs.
 *
 * The switch label is the HONEST agent-derived state (Rule 44): a not-yet-paired
 * node shows "Pair on LAN" and the switch is disabled (Rule 47 — never offer a
 * control that cannot reach the node); a reachable node shows Off / Enabling /
 * Enabled / Running from the drone's own readiness.
 *
 * @license GPL-3.0-only
 */

import { useState } from "react";

import { deviceIdFromNodeId } from "@/lib/agent/node-id";
import { useAtlasControl } from "@/hooks/use-atlas-control";
import { useNodeFeaturesStore } from "@/stores/node-features-store";
import { Toggle } from "@/components/ui/toggle";

export function WorldModelFeatureRow({ droneId }: { droneId: string }) {
  const deviceId = deviceIdFromNodeId(droneId) ?? droneId;
  const enabled = useNodeFeaturesStore((s) =>
    (s.enabled[deviceId] ?? []).includes("world-model"),
  );
  const setEnabled = useNodeFeaturesStore((s) => s.setEnabled);
  const control = useAtlasControl(droneId);
  const [busy, setBusy] = useState(false);

  const available = control.demo || control.reachable;
  const r = control.readiness;

  const status = !available
    ? "Pair on LAN"
    : !enabled
      ? "Off"
      : r?.serviceRunning || r?.capturing
        ? "Running"
        : r?.enabled
          ? "Enabled"
          : "Enabling…";

  const onToggle = async (on: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      if (on) {
        // Reveal the tabs + start the poll first, then enable the service so
        // the readiness poll confirms it came up.
        setEnabled(deviceId, "world-model", true);
        await control.enable();
      } else {
        await control.disable();
        setEnabled(deviceId, "world-model", false);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Toggle
      label={busy || control.busy ? "Working…" : status}
      checked={enabled}
      onChange={onToggle}
      disabled={!available || busy || control.busy}
    />
  );
}
