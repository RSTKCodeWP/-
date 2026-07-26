/**
 * @module video/webrtc/peer-utils
 * @description Shared peer-connection lifecycle helpers: ICE restart
 * with cooldown, and the health reporter that fans transport-attempt
 * state into the video store. The `closePeerConnection` helper itself
 * lives in `../webrtc-client.ts` so the cleanup-contract regression
 * test can source-scan a single file; this module re-exports it under
 * its canonical name for the per-flow modules to consume.
 * @license GPL-3.0-only
 */

import {
  useVideoStore,
  type TransportAttemptStage,
  type TransportErrorCode,
  type VideoTransport,
} from "@/stores/video-store";
import { closePeerConnection as closePeerConnectionImpl } from "../webrtc-client";
import { getPc } from "./session-state";

export const closePeerConnection = closePeerConnectionImpl;

// ICE restart cooldown: only attempt once per 5 seconds to
// avoid thrash on flapping networks.
let lastIceRestartAt = 0;

/**
 * Attempt an ICE restart against the given peer connection. Refuses
 * when the connection has been replaced by a newer one (cascade may
 * have moved on to a different transport) or when the cooldown is
 * still active.
 */
export function tryIceRestart(targetPc: RTCPeerConnection): void {
  if (targetPc !== getPc()) return; // a newer pc has taken over
  if (targetPc.connectionState === "closed") return;
  if (typeof targetPc.restartIce !== "function") return; // older browsers
  const now = Date.now();
  if (now - lastIceRestartAt < 5000) return;
  lastIceRestartAt = now;
  try {
    targetPc.restartIce();
    console.log("[webrtc-client] ICE restart triggered after disconnect");
  } catch (err) {
    console.warn("[webrtc-client] ICE restart failed:", err);
  }
}

export function resetIceRestartCooldown(): void {
  lastIceRestartAt = 0;
}

/**
 * Report a per-transport health update into the video store. Used by
 * each per-flow module to thread the cascade UX (testing → ok → failed)
 * out of its inner control flow.
 */
export function reportHealth(
  transport: VideoTransport,
  patch: {
    state?: "testing" | "ok" | "failed";
    stage?: TransportAttemptStage;
    code?: TransportErrorCode;
    error?: string;
    connectMs?: number;
  },
): void {
  useVideoStore.getState().setTransportHealth(transport, {
    state: patch.state,
    lastAttemptStage: patch.stage ?? null,
    lastErrorCode: patch.code ?? null,
    lastError: patch.error ?? null,
    connectMs: patch.connectMs ?? null,
  });
}
