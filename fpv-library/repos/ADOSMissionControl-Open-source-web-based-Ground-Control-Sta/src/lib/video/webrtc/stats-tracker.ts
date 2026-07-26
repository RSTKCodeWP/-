/**
 * @module video/webrtc/stats-tracker
 * @description WebRTC stats polling. Computes fps, network RTT, decoder
 * jitter buffer wait, codec name, bitrate, and packet loss from a
 * periodic `pc.getStats()` sweep, then publishes a single atomic patch
 * to the video store.
 *
 * The polling state (`lastFramesDecoded`, `lastStatsTime`, etc.) lives
 * in `useVideoStore._pollState` so Turbopack HMR re-evaluating this
 * module does not reset the deltas to 0 mid-session.
 *
 * @license GPL-3.0-only
 */

import { useVideoStore } from "@/stores/video-store";
import { getPc } from "./session-state";

let statsInterval: ReturnType<typeof setInterval> | null = null;

// Frozen-stream watchdog window. If neither framesDecoded nor
// bytesReceived advances for this long while pc.connectionState stays
// "connected", the stream has silently stalled (decoder wedge, transport
// freeze) without any connectionstatechange event. We tear down and
// re-fetch the offer.
const FROZEN_STREAM_TIMEOUT_MS = 7000;

// The watchdog only arms outside development. Turbopack HMR re-evaluates
// modules on unrelated edits, which can momentarily flatten the deltas and
// produce a false stall. In production there is no HMR, so the watchdog is
// safe to arm.
const WATCHDOG_ARMED = process.env.NODE_ENV === "production";

// When the page is hidden the browser legitimately pauses frame
// production for a backgrounded <video>. We reset the progress baseline on
// every visibility change so the watchdog never fires for a tab the user
// simply switched away from. Registered once per polling session.
let visibilityHandler: (() => void) | null = null;

function armVisibilityReset(): void {
  if (typeof document === "undefined" || visibilityHandler) return;
  visibilityHandler = () => {
    useVideoStore.getState().setPollState({ lastProgressTime: Date.now() });
  };
  document.addEventListener("visibilitychange", visibilityHandler);
}

function disarmVisibilityReset(): void {
  if (typeof document === "undefined" || !visibilityHandler) return;
  document.removeEventListener("visibilitychange", visibilityHandler);
  visibilityHandler = null;
}

/**
 * Stop polling, tear down the active stream, and raise the stall signal
 * so the owning video surface re-fetches the offer with backoff. Mirrors
 * the "failed"-path teardown in the per-flow modules (setStreaming(false)
 * + stopStatsPolling) and adds the one-way stall edge that the cascade
 * hook watches.
 */
function handleFrozenStream(): void {
  const store = useVideoStore.getState();
  stopStatsPolling();
  store.setStreaming(false);
  store.updateStats(0, 0);
  store.signalVideoStall();
}

/** Begin the 1 Hz stats poll. Idempotent. */
export function startStatsPolling(): void {
  if (statsInterval) return;

  // Reset polling state in the HMR-safe Zustand store
  useVideoStore.getState().resetPollState();
  useVideoStore.getState().setPollState({
    lastFrameTime: Date.now(),
    lastProgressTime: Date.now(),
  });
  armVisibilityReset();

  statsInterval = setInterval(async () => {
    const pc = getPc();
    if (!pc) return;

    const stats = await pc.getStats();
    const store = useVideoStore.getState();
    // Read persistent polling state from store
    const ps = store._pollState;
    const lastFramesDecoded = ps.lastFramesDecoded;
    const lastStatsTime = ps.lastStatsTime;
    const lastBytesReceived = ps.lastBytesReceived;
    const lastJitterDelay = ps.lastJitterDelay;
    const lastJitterEmitted = ps.lastJitterEmitted;

    // Single pass over the stats report. Collect codec entries by id while
    // also processing inbound-rtp and candidate-pair entries. Codec name is
    // resolved after the loop so we don't depend on iteration order.
    type CodecStatsLite = { id: string; type: string; mimeType?: string };
    const codecReports = new Map<string, CodecStatsLite>();

    let computedFps = 0;
    let inboundFound = false;
    let jitterMs = 0;
    let rttMs = 0;
    let framesDecoded = 0;
    let framesDropped = 0;
    let codecName = "";
    let bitrateKbps = 0;
    let packetsLost = 0;
    let inboundJitterRtpMs = 0;
    let bytesReceived = 0;
    let inboundCodecId: string | undefined;

    stats.forEach((report) => {
      if (report.type === "codec") {
        codecReports.set(report.id, report as unknown as CodecStatsLite);
        return;
      }

      if (report.type === "inbound-rtp" && report.kind === "video") {
        inboundFound = true;

        type ExtendedInbound = RTCInboundRtpStreamStats & {
          framesPerSecond?: number;
          framesDecoded?: number;
          framesDropped?: number;
          jitterBufferDelay?: number;
          jitterBufferEmittedCount?: number;
          codecId?: string;
          bytesReceived?: number;
          packetsLost?: number;
          jitter?: number;
        };
        const r = report as ExtendedInbound;

        // Prefer the browser-reported framesPerSecond, fall back to derived
        const reportedFps = r.framesPerSecond;
        const decoded = r.framesDecoded ?? 0;
        framesDecoded = decoded;
        framesDropped = r.framesDropped ?? 0;
        const now = Date.now();

        if (reportedFps !== undefined && reportedFps > 0) {
          computedFps = Math.round(reportedFps);
        } else if (lastStatsTime > 0 && decoded > lastFramesDecoded) {
          const elapsedSec = (now - lastStatsTime) / 1000;
          if (elapsedSec > 0) {
            computedFps = Math.round((decoded - lastFramesDecoded) / elapsedSec);
          }
        }

        // Decoder jitter buffer (L5). Use the delta over the last polling
        // window instead of the cumulative average. The cumulative ratio
        // gets pinned to whatever the buffer looked like during the
        // connection ramp-up, even if the stream is now smooth.
        const delay = r.jitterBufferDelay ?? 0;
        const emitted = r.jitterBufferEmittedCount ?? 0;
        if (emitted > lastJitterEmitted && lastJitterEmitted > 0) {
          const deltaDelay = delay - lastJitterDelay;
          const deltaEmitted = emitted - lastJitterEmitted;
          if (deltaEmitted > 0) {
            jitterMs = Math.round((deltaDelay / deltaEmitted) * 1000);
          }
        } else if (emitted > 0 && lastJitterEmitted === 0) {
          // First sample. Use cumulative as best available.
          jitterMs = Math.round((delay / emitted) * 1000);
        }
        // Persist for next window. Local mutation only; we batch the
        // store write at the bottom of this poll cycle.
        ps.lastJitterDelay = delay;
        ps.lastJitterEmitted = emitted;

        // Capture codec id; resolve mimeType after the loop completes.
        inboundCodecId = r.codecId;
        bytesReceived = r.bytesReceived ?? 0;
        packetsLost = r.packetsLost ?? 0;
        // r.jitter is in seconds (per spec)
        inboundJitterRtpMs = Math.round((r.jitter ?? 0) * 1000);
        return;
      }

      if (
        report.type === "candidate-pair" &&
        (report as RTCIceCandidatePairStats).state === "succeeded" &&
        (report as RTCIceCandidatePairStats).nominated
      ) {
        // Network round-trip (L4). Browser to mediamtx.
        const rttSec = (report as RTCIceCandidatePairStats).currentRoundTripTime ?? 0;
        rttMs = Math.round(rttSec * 1000);
      }
    });

    // Resolve codec mimeType after the single pass so iteration order
    // does not matter.
    if (inboundCodecId && codecReports.has(inboundCodecId)) {
      const codec = codecReports.get(inboundCodecId)!;
      // mimeType looks like "video/H264" or "video/VP8"
      const mime = codec.mimeType || "";
      codecName = mime.includes("/") ? mime.split("/")[1] : mime;
    }

    if (inboundFound) {
      // Roll-up latency = network RTT + decoder jitter buffer wait.
      // Keep updateStats(fps, latencyMs) for the existing badge readers
      // that only want a single number. The richer breakdown below
      // gives the popover what it needs to attribute time correctly.
      const totalLatencyMs = rttMs + jitterMs;
      store.updateStats(computedFps, totalLatencyMs);

      store.setReceiveLatency({
        rttMs,
        jitterBufferMs: jitterMs,
        rtpJitterMs: inboundJitterRtpMs,
        framesDecoded,
        framesDropped,
      });

      // Bitrate from byte delta over the polling interval
      if (lastStatsTime > 0 && bytesReceived > lastBytesReceived) {
        const elapsedSec = (Date.now() - lastStatsTime) / 1000;
        if (elapsedSec > 0) {
          const deltaBytes = bytesReceived - lastBytesReceived;
          bitrateKbps = Math.round((deltaBytes * 8) / elapsedSec / 1000);
        }
      }

      store.setVideoMetrics({
        codec: codecName,
        bitrateKbps,
        packetsLost,
        jitterMs: inboundJitterRtpMs > 0 ? inboundJitterRtpMs : jitterMs,
      });

      // Did anything actually advance this window? Either the decoder
      // consumed a new frame or the transport delivered new bytes. Used
      // by the frozen-stream watchdog below.
      const progressed =
        framesDecoded > lastFramesDecoded || bytesReceived > lastBytesReceived;

      // Persist polling state to the Zustand store. This single
      // setPollState call replaces module-global writes — the store is
      // HMR-safe so the next poll cycle (even after a Turbopack reload
      // of this module) reads the correct previous values.
      store.setPollState({
        lastFramesDecoded: framesDecoded,
        lastBytesReceived: bytesReceived,
        lastStatsTime: Date.now(),
        lastJitterDelay: ps.lastJitterDelay,
        lastJitterEmitted: ps.lastJitterEmitted,
        lastFrameTime: computedFps > 0 ? Date.now() : ps.lastFrameTime,
        lastProgressTime: progressed ? Date.now() : ps.lastProgressTime,
      });
    }

    // Frozen-stream watchdog. The native pc.onconnectionstatechange
    // handler detects transport-level disconnects, but a decoder wedge or
    // a silently-frozen transport keeps connectionState at "connected"
    // while frames and bytes both stop advancing — the user sees a frozen
    // last frame with no error. When neither counter has moved for the
    // timeout window, tear down and re-fetch the offer. The previous
    // frame-arrival timeout was removed because it false-triggered under
    // Turbopack HMR; this version only arms in production and resets its
    // baseline on visibility change, so the two failure modes do not
    // overlap.
    // A hidden tab legitimately pauses frame production for a backgrounded
    // <video>. Skip the stall judgement entirely while hidden, independent
    // of the visibilitychange baseline reset — a poll tick can race the
    // reset and otherwise misfire on the first tick after the tab un-hides.
    const pageHidden = typeof document !== "undefined" && document.hidden;
    if (WATCHDOG_ARMED && !pageHidden && pc.connectionState === "connected") {
      const sinceProgressMs = Date.now() - useVideoStore.getState()._pollState.lastProgressTime;
      if (sinceProgressMs > FROZEN_STREAM_TIMEOUT_MS) {
        handleFrozenStream();
      }
    }
  }, 1000);
}

export function stopStatsPolling(): void {
  if (statsInterval) {
    clearInterval(statsInterval);
    statsInterval = null;
  }
  disarmVisibilityReset();
}
