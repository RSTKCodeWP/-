"use client";

/**
 * @module vision/WhatsLockedChip
 * @description The "what's locked" chip — a faithful port of the reference
 * artifact's `.lockchip` (icon tile · who/state · range). The single, shared,
 * honest readout of the operator-designated target: class + track id, its LIVE
 * lock state (read from the detection stream by track id, not a stale copy),
 * and confidence. Shown only while a target is selected on this drone. Styling
 * is the artifact's (`.ados-cockpit .lockchip`).
 *
 * Honest "why did the lock go away" (Rule 44): when the designated target's
 * lock drops, the operator needs to know WHETHER the tracker lost the target
 * (the feed is live, the object left the frame / could not be re-associated) or
 * the PERCEPTION FEED itself went stale / the offload link dropped (we simply
 * can't see anymore). Those are very different situations, so the chip reads the
 * same {@link DETECTION_STALE_MS} freshness the box overlay uses: a live feed
 * shows the tracker's own lock state, a stale feed shows "Feed stale" /
 * "Offload link lost" and stops trusting the last (now stale) detection.
 *
 * @license GPL-3.0-only
 */

import { useEffect, useState } from "react";
import { Crosshair } from "lucide-react";

import { perceptionFeedState, staleReason } from "@/lib/vision/perception-health";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import {
  useVisionDetectionsStore,
  type LockState,
} from "@/stores/vision-detections-store";
import { useSelectedTargetStore } from "@/stores/selected-target-store";

/** Human label for a live lock state. */
function lockLabel(state: LockState | null): string {
  switch (state) {
    case "locked":
      return "Locked";
    case "uncertain":
      return "Uncertain";
    case "lost":
      return "Lost";
    default:
      return "Selected";
  }
}

export function WhatsLockedChip({ droneId }: { droneId: string }) {
  const selected = useSelectedTargetStore((s) => s.selected);
  const batch = useVisionDetectionsStore((s) => s.batches[droneId]);
  const tier = useAgentCapabilitiesStore((s) => s.perceptionTier);

  const [now, setNow] = useState(() => Date.now());

  // Age the feed on its own so the chip flips a lock to "feed stale" when the
  // stream stops, not only when a fresh batch happens to arrive. Runs only
  // while a feed has started; hooks stay above the early return (Rules of Hooks).
  // Key on whether a feed EXISTS, not the batch object (replaced every frame,
  // ~10-15 Hz), so the 500 ms interval is created once per feed lifecycle.
  const hasFeed = !!batch;
  useEffect(() => {
    if (!hasFeed) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [hasFeed]);

  const here = selected && selected.droneId === droneId ? selected : null;
  if (!here) return null;

  const feed = perceptionFeedState(batch, now);
  const stale = feed === "stale";

  // Only trust a detection while the feed is fresh — a stale batch's last box is
  // not "live", so it must not masquerade as a current lock state / confidence.
  const live =
    feed === "fresh" && here.trackId != null && batch
      ? batch.detections.find((d) => d.trackId === here.trackId)
      : undefined;

  // A stale feed overrides the tracker's (now stale) lock label with the honest
  // reason we lost sight — the offload link dropped, or the local feed went quiet.
  const label = stale ? staleReason(tier) : lockLabel(live?.lockState ?? null);
  const confidence = live?.confidence ?? here.confidence;
  const who =
    here.trackId != null
      ? `${here.classLabel} · trk ${here.trackId}`
      : here.classLabel;

  return (
    <div
      className="lockchip"
      style={{
        left: "50%",
        top: 48,
        transform: "translateX(-50%)",
        ...(stale
          ? { borderColor: tier === "offload" ? "var(--crit)" : "var(--warn)" }
          : {}),
      }}
      data-cockpit-widget="whats-locked"
      data-feed-state={feed}
    >
      <div className="ic">
        <Crosshair size={14} aria-hidden="true" />
      </div>
      <div className="who">
        <b>{who}</b>
        <span style={stale ? { color: tier === "offload" ? "var(--crit)" : "var(--warn)" } : undefined}>
          {label}
        </span>
      </div>
      <div className="rng">
        {Math.round(confidence * 100)}%<small>conf</small>
      </div>
    </div>
  );
}
