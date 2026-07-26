"use client";

/**
 * @module VisionDetectionsBridge
 * @description Always-mounted, route-agnostic opener for the per-drone detection
 * WebSocket — the detection-feed counterpart of `CloudStatusBridge` (which does
 * the same for the WHEP video host). It resolves the SELECTED drone's LAN host +
 * pairing key LOCAL-FIRST from `local-nodes-store` (by device id) and opens
 * `connectVisionDetections`, so bounding boxes flow for a locally-paired drone
 * regardless of which tab is showing — instead of depending on
 * `useAgentConnectionStore.agentUrl`, which the cockpit's own opener gated on and
 * which is null for a LAN pairing. Renders null; no-op in demo (the mock stream
 * feeds the store directly) and until a reachable host + selected drone exist.
 *
 * On an HTTPS origin `resolveLanAgentUrl` returns null (a browser can't `ws://`
 * a private LAN host from an https page — mixed content); that path is served by
 * the cloud-relay detection topic (a documented additive follow-up). This bridge
 * fully closes the HTTP dev / Electron / LAN-served case.
 * @license GPL-3.0-only
 */

import { useEffect, useMemo } from "react";

import { useDroneManager } from "@/stores/drone-manager";
import { useLocalNodesStore } from "@/stores/local-nodes-store";
import { deviceIdFromNodeId } from "@/lib/agent/node-id";
import {
  resolveLanAgentUrl,
  resolvePairedApiKey,
} from "@/stores/agent-connection/cloud-state";
import { connectVisionDetections } from "@/lib/agent/vision-detections-ws";

export function VisionDetectionsBridge() {
  const selectedDroneId = useDroneManager((s) => s.selectedDroneId);
  // Subscribe to the local-nodes set so the feed reconnects the moment a node's
  // host/key appears or changes (e.g. just after a local pairing).
  const nodes = useLocalNodesStore((s) => s.nodes);

  const target = useMemo(() => {
    const deviceId = selectedDroneId ? deviceIdFromNodeId(selectedDroneId) : null;
    if (!selectedDroneId || !deviceId) {
      return { droneId: null as string | null, agentUrl: null as string | null, apiKey: null as string | null };
    }
    // `nodes` is the reactivity trigger; the resolvers read the same store.
    return {
      droneId: selectedDroneId,
      agentUrl: resolveLanAgentUrl(deviceId),
      apiKey: resolvePairedApiKey(deviceId),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDroneId, nodes]);

  useEffect(() => {
    if (!target.droneId || !target.agentUrl) return;
    const conn = connectVisionDetections({
      droneId: target.droneId,
      agentUrl: target.agentUrl,
      apiKey: target.apiKey,
    });
    return () => conn.close();
  }, [target.droneId, target.agentUrl, target.apiKey]);

  return null;
}
