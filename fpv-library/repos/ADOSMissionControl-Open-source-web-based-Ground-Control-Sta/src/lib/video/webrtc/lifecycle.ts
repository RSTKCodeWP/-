/**
 * @module video/webrtc/lifecycle
 * @description Cross-flow lifecycle helpers: stop the active stream,
 * bind a video element for screenshot/recording reference, and the
 * is-stream-active probe that consumers use to gate UI affordances.
 * @license GPL-3.0-only
 */

import { useVideoStore } from "@/stores/video-store";
import { closePeerConnection, resetIceRestartCooldown } from "./peer-utils";
import { detachSeiTransform, bindFrameCallback } from "./sei-transform";
import {
  getMediaRecorder,
  getPc,
  setPc,
  setVideoElementRef,
} from "./session-state";
import { stopStatsPolling } from "./stats-tracker";
import { stopRecording } from "./recording";

/** Stop the active WebRTC stream. */
export async function stopStream(): Promise<void> {
  const store = useVideoStore.getState();

  if (getMediaRecorder()?.state === "recording") {
    stopRecording();
  }

  stopStatsPolling();
  detachSeiTransform();

  const current = getPc();
  if (current) {
    // closePeerConnection nulls handlers, stops every receiver+sender
    // track (Safari camera-stuck fix), then closes the connection.
    closePeerConnection(current);
    setPc(null);
  }

  // Reset ICE restart cooldown so the next session can restart immediately
  // instead of being gated by the previous session's 5s cooldown.
  resetIceRestartCooldown();

  store.setStreaming(false);
  store.setStreamUrl(null);
  store.updateStats(0, 0);
  store.setTransport("unknown");
  store.setVideoMetrics({ codec: "", bitrateKbps: 0, packetsLost: 0, jitterMs: 0 });
  store.resetLatency();
}

// Tracks the element + handler for the loadedmetadata listener so a re-bind
// or unbind detaches the previous one instead of stacking listeners on a
// reused <video> element across mounts.
let metadataEl: HTMLVideoElement | null = null;
let metadataHandler: (() => void) | null = null;

/** Bind a video element for screenshot/recording reference. */
export function setVideoElement(el: HTMLVideoElement | null): void {
  setVideoElementRef(el);

  if (metadataEl && metadataHandler) {
    metadataEl.removeEventListener("loadedmetadata", metadataHandler);
    metadataEl = null;
    metadataHandler = null;
  }

  if (el) {
    // Track resolution changes
    metadataEl = el;
    metadataHandler = () => {
      useVideoStore
        .getState()
        .setResolution(`${el.videoWidth}x${el.videoHeight}`);
    };
    el.addEventListener("loadedmetadata", metadataHandler);
    // Hook requestVideoFrameCallback for the SEI-driven true G2G
    // computation. No-op when the browser lacks the API.
    bindFrameCallback(el);
  }
}

/** Check if a stream is currently active. */
export function isStreamActive(): boolean {
  const current = getPc();
  return current !== null && current.connectionState === "connected";
}
