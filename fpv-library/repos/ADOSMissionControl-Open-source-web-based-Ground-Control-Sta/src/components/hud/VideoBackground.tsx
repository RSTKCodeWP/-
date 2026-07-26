"use client";

// HUD video background. Full-viewport WebRTC/WHEP feed. Reuses the same
// cascade hook and webrtc-client helpers as VideoFeedCard, but renders a
// bare <video> element sized to cover the kiosk display with no chrome.
// Supports two transports: LAN Direct WHEP and P2P MQTT.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVideoStore } from "@/stores/video-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useVideoTransportCascade } from "@/hooks/use-video-transport-cascade";

// Kiosk auto-recovery backoff. The HUD has no operator to press a retry
// button, so it must re-cascade itself indefinitely whenever the link
// drops or silently stalls. Backoff doubles per attempt, clamped at the
// ceiling, and keeps retrying at the ceiling forever.
const HUD_RETRY_BASE_DELAY_SEC = 3;
const HUD_RETRY_MAX_DELAY_SEC = 30;

export function VideoBackground() {
  const agentWhepUrl = useVideoStore((s) => s.agentWhepUrl);
  const agentVideoState = useVideoStore((s) => s.agentVideoState);
  const isStreaming = useVideoStore((s) => s.isStreaming);
  const videoStallSignal = useVideoStore((s) => s.videoStallSignal);
  const cloudDeviceId = useAgentConnectionStore((s) => s.cloudDeviceId);
  const transportMode = useSettingsStore((s) => s.videoTransportMode);

  // Callback ref so the cascade hook re-runs once the <video> mounts.
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  const setVideoRef = useCallback((el: HTMLVideoElement | null) => {
    setVideoEl(el);
  }, []);

  // Re-cascade key. The HUD previously pinned this at 0, so a failed
  // transport looped the same dead attempt forever. Bumping it on failure
  // (and on a stall signal) forces the cascade hook to re-fetch the offer.
  const [retryKey, setRetryKey] = useState(0);
  const retryAttemptRef = useRef(0);

  // Stabilize enabled: require 3 consecutive non-running polls before
  // disabling the cascade. Mirrors VideoFeedCard so a flaky agent probe
  // does not kill a healthy WebRTC session on the kiosk.
  const nonRunningCountRef = useRef(0);
  const stableEnabled = useMemo(() => {
    if (agentVideoState === "running") {
      nonRunningCountRef.current = 0;
      return true;
    }
    nonRunningCountRef.current += 1;
    return nonRunningCountRef.current < 3;
  }, [agentVideoState]);

  const cascade = useVideoTransportCascade({
    agentWhepUrl,
    cloudDeviceId,
    transportMode,
    videoEl,
    retryKey,
    enabled: stableEnabled,
  });

  // Reset backoff once the kiosk is streaming again.
  useEffect(() => {
    if (cascade.state === "connected") {
      retryAttemptRef.current = 0;
    }
  }, [cascade.state]);

  // Indefinite backoff re-cascade on failure. No operator, no cap.
  useEffect(() => {
    if (cascade.state !== "failed" || agentVideoState !== "running") {
      return;
    }
    const delaySec = Math.min(
      HUD_RETRY_BASE_DELAY_SEC * Math.pow(2, retryAttemptRef.current),
      HUD_RETRY_MAX_DELAY_SEC,
    );
    const handle = setTimeout(() => {
      retryAttemptRef.current += 1;
      setRetryKey((k) => k + 1);
    }, delaySec * 1000);
    return () => clearTimeout(handle);
  }, [cascade.state, agentVideoState]);

  // Frozen-stream signal: re-cascade immediately to re-fetch the offer.
  const lastHandledStallRef = useRef(videoStallSignal);
  useEffect(() => {
    if (videoStallSignal === lastHandledStallRef.current) return;
    lastHandledStallRef.current = videoStallSignal;
    if (agentVideoState !== "running") return;
    setRetryKey((k) => k + 1);
  }, [videoStallSignal, agentVideoState]);

  const hasVideo = isStreaming;
  const connecting = cascade.state === "connecting" || agentVideoState === "starting";

  return (
    <div className="absolute inset-0 bg-black">
      <video
        ref={setVideoRef}
        autoPlay
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover bg-black"
      />
      {!hasVideo && (
        <div className="absolute inset-0 flex items-center justify-center text-white/30 text-xs font-mono uppercase tracking-widest pointer-events-none">
          {connecting
            ? "connecting video..."
            : cascade.state === "failed"
              ? "video link down"
              : "no video signal"}
        </div>
      )}
    </div>
  );
}
