/**
 * @module video/webrtc/whep-flow
 * @description LAN-direct WHEP path. The cascade hook calls `startStream`
 * when attempting the `lan-whep` mode; this module handles the SDP
 * exchange against mediamtx, ICE gathering, ontrack wait, and the
 * receiver-side latency hints.
 * @license GPL-3.0-only
 */

import { useVideoStore, type VideoTransport } from "@/stores/video-store";
import {
  LAN_ICE_GATHER_TIMEOUT_MS,
  LAN_ONTRACK_TIMEOUT_MS,
} from "../webrtc-constants";
import {
  abortable,
  checkAborted,
  classifyError,
} from "../webrtc-helpers";
import {
  closePeerConnection,
  reportHealth,
  tryIceRestart,
} from "./peer-utils";
import { attachSeiTransform } from "./sei-transform";
import { getPc, setPc } from "./session-state";
import { startStatsPolling, stopStatsPolling } from "./stats-tracker";

/**
 * Start a WebRTC stream from a WHEP endpoint.
 *
 * @param whepUrl — Full WHEP URL, e.g. `http://192.168.1.50:8889/stream/whep`
 * @param signal  — Optional AbortSignal. When fired, the function aborts at
 *                  the next checkpoint and throws AbortError. Used by the
 *                  cascade hook to cancel a mode mid-attempt without
 *                  leaving a stale background continuation.
 * @returns The MediaStream to attach to a <video> element.
 */
export async function startStream(
  whepUrl: string,
  signal?: AbortSignal,
): Promise<MediaStream> {
  const store = useVideoStore.getState();
  const startedAt = Date.now();
  // startStream is the LAN-direct WHEP path; the cascade hook only calls
  // it when attempting lan-whep. The URL itself may be a Cloudflare
  // tunnel (relay.altnautica.com) on cloud-routed deployments, but the
  // *mode* the cascade attached to is still lan-whep. Trust the cascade,
  // not detectTransportFromUrl which mis-classifies tunneled URLs.
  const transport: VideoTransport = "lan-whep";

  // Report testing state for the cascade UX
  reportHealth(transport, { state: "testing", stage: "starting" });

  // Clean up any stale connection before starting fresh
  const existing = getPc();
  if (existing) {
    closePeerConnection(existing);
    setPc(null);
    stopStatsPolling();
  }

  // Hold a local reference so handlers can verify they're still the
  // active pc. The module-level `pc` may be replaced by a parallel call
  // (e.g. cascade switching modes) and we don't want stale handlers to
  // operate on the wrong connection.
  let localPc: RTCPeerConnection | null = null;

  try {
    checkAborted(signal);

    const newPc = new RTCPeerConnection({
      iceServers: [], // Local network — no STUN/TURN needed
    });
    localPc = newPc;
    setPc(newPc);

    // Capture newPc (a const) in the handler closure. Even if a
    // parallel call replaces the global pc, this handler still refers
    // to ITS OWN connection, and bails on the (newPc !== getPc())
    // check.
    newPc.onconnectionstatechange = () => {
      if (newPc !== getPc()) return; // a newer pc has taken over
      const state = newPc.connectionState;
      if (state === "disconnected") {
        console.warn("[webrtc-client] LAN WHEP disconnected — attempting ICE restart");
        tryIceRestart(newPc);
      } else if (state === "failed" || state === "closed") {
        console.warn("[webrtc-client] LAN WHEP terminal state:", state);
        const s = useVideoStore.getState();
        s.setStreaming(false);
        s.updateStats(0, 0);
        stopStatsPolling();
        reportHealth(transport, {
          state: "failed",
          stage: "connected",
          code: "ice-disconnect",
          error: `Connection ${state}`,
        });
      }
    };

    // Receive-only transceiver. Capture the video transceiver so the
    // receiver-side playout hints can be set before negotiation begins.
    //
    // playoutDelayHint=0: the default RTCRtpReceiver targets a playout
    // buffer in the 100-200 ms range for live streams. With a healthy
    // LAN link this is pure latency tax; the value is a hint (not a
    // hard ceiling) so the stack still grows the buffer if jitter
    // demands it. Browsers that don't implement the property ignore
    // the assignment (silent no-op via property check).
    //
    // jitterBufferTarget=50: Chrome-only and experimental, sets a
    // preferred lower bound on the jitter buffer in ms. 50 ms is the
    // FPV-grade default; on a flaky link the buffer still expands
    // automatically. Strictly additive to playoutDelayHint.
    //
    // Distinct from the previously-removed mungeForLowLatency() SDP
    // hack. That mechanism pinned Chrome's MINIMUM jitter buffer via
    // the conference flag and caused decoder stalls on WiFi
    // reordering. These are *receiver-side runtime properties* — they
    // suggest a target without forcing a hard floor — so the failure
    // mode of the prior approach does not apply.
    const videoTransceiver = localPc.addTransceiver("video", {
      direction: "recvonly",
    });
    try {
      const recv = videoTransceiver.receiver as RTCRtpReceiver & {
        playoutDelayHint?: number;
        jitterBufferTarget?: number;
      };
      if ("playoutDelayHint" in recv) {
        recv.playoutDelayHint = 0;
      }
      if ("jitterBufferTarget" in recv) {
        recv.jitterBufferTarget = 50;
      }
    } catch (err) {
      // Browser without the receiver-side hint API — log once and
      // continue. Default Chrome / Edge / Opera support it; older
      // Firefox and Safari builds fall back to their internal
      // defaults.
      console.debug(
        "[webrtc-client] receiver-side latency hints unavailable",
        err,
      );
    }
    localPc.addTransceiver("audio", { direction: "recvonly" });

    const offer = await abortable(localPc.createOffer(), signal);
    checkAborted(signal);
    await abortable(localPc.setLocalDescription(offer), signal);
    checkAborted(signal);

    // Wait for ICE gathering to complete (or LAN_ICE_GATHER_TIMEOUT_MS)
    await new Promise<void>((resolve) => {
      if (localPc!.iceGatheringState === "complete") {
        resolve();
        return;
      }
      const check = () => {
        if (localPc?.iceGatheringState === "complete") {
          localPc.removeEventListener("icegatheringstatechange", check);
          resolve();
        }
      };
      localPc!.addEventListener("icegatheringstatechange", check);
      setTimeout(resolve, LAN_ICE_GATHER_TIMEOUT_MS);
    });
    checkAborted(signal);

    // SDP offer — send as-is. The previous mungeForLowLatency() injected
    // a=x-google-flag:conference which pins Chrome to a minimum jitter
    // buffer. That flag is designed for multi-party conferences on
    // reliable networks, not one-way WHEP streaming over WiFi. On WiFi
    // with any jitter or reordering, the minimum buffer causes decoder
    // stalls that appear as video freezes after a few seconds. mediamtx's
    // own test page (no SDP munge) streams indefinitely.
    const offerSdp = localPc.localDescription!.sdp;

    // Send offer to WHEP endpoint (fetch supports AbortSignal natively)
    const response = await fetch(whepUrl, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: offerSdp,
      signal,
    });

    if (!response.ok) {
      const msg = response.status === 404
        ? "No video stream on agent (mediamtx 404, video pipeline not running)"
        : `WHEP request failed: ${response.status} ${response.statusText}`;
      throw new Error(msg);
    }

    const answerSdp = await abortable(response.text(), signal);
    checkAborted(signal);

    // Set ontrack BEFORE setRemoteDescription to avoid race condition
    // (track events can fire during or immediately after setRemoteDescription)
    const trackPromise = new Promise<MediaStream>((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error(`No video track received within ${LAN_ONTRACK_TIMEOUT_MS / 1000}s`)),
        LAN_ONTRACK_TIMEOUT_MS,
      );
      localPc!.ontrack = (event) => {
        if (event.streams[0]) {
          clearTimeout(timeout);
          resolve(event.streams[0]);
        }
      };
    });

    await abortable(localPc.setRemoteDescription({ type: "answer", sdp: answerSdp }), signal);
    const stream = await abortable(trackPromise, signal);
    checkAborted(signal);

    store.setStreamUrl(whepUrl);
    store.setStreaming(true);
    // Classify and publish the active transport so the UI can show
    // "LAN DIRECT" / "CLOUD WHEP" badges.
    store.setTransport(transport);
    // Report success with connection establishment time (NOT live RTT,
    // which is tracked separately).
    reportHealth(transport, {
      state: "ok",
      stage: "connected",
      connectMs: Date.now() - startedAt,
    });

    // Start stats polling
    startStatsPolling();
    // Attach SEI script transform on the receiver to enable true
    // camera→monitor latency. Pass-through only — never modifies
    // frames; no-ops on browsers without RTCRtpScriptTransform.
    attachSeiTransform(localPc);

    return stream;
  } catch (err) {
    // Tear down the local pc on any failure. Only clear the global if we're
    // still the active pc (a parallel call may have already replaced us).
    if (localPc) {
      closePeerConnection(localPc);
      if (localPc === getPc()) setPc(null);
    }
    const { code, message } = classifyError(err);
    reportHealth(transport, { state: "failed", code, error: message });
    throw err;
  }
}
