"use client";

/**
 * @module vision/TargetLeadReticle
 * @description Draws a LEAD reticle for the operator-designated target: a ghost
 * reticle a fixed time ahead of a MOVING, tracked target plus the lead vector
 * from its current centre. It reads the target's real per-frame motion from the
 * detection stream and projects it forward — an aim-ahead cue for a mover, and
 * the same lead a gimbal/behaviour would use.
 *
 * It composites through the shared mark layer (pushes marks into
 * `cockpit-marks-store` under one source id; {@link CockpitMarkLayer} draws
 * them letterbox-correct) rather than stacking its own overlay.
 *
 * Honest (Rule 44): the reticle appears only for a tracked target on a FRESH
 * feed with real, measurable motion. It clears the moment the target is
 * deselected, the track drops, the feed goes stale, or the target stops — never
 * a fabricated heading for a still or lost target. Renders nothing itself.
 *
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";

import type { CockpitMark } from "@/lib/cockpit/marks";
import {
  LEAD_HISTORY_MS,
  LEAD_MS,
  MIN_LEAD_SPEED_PX_PER_SEC,
  computeLead,
  pushLeadSample,
  type TrackSample,
} from "@/lib/vision/target-lead";
import {
  DETECTION_STALE_MS,
  useVisionDetectionsStore,
} from "@/stores/vision-detections-store";
import { useSelectedTargetStore } from "@/stores/selected-target-store";
import { useCockpitMarksStore } from "@/stores/cockpit-marks-store";

/** Stable mark-source id (one owner of the lead marks). */
const SOURCE = "builtin.target-lead";
/** Amber "aim ahead", deliberately distinct from the green designated-lock box. */
const LEAD_COLOR = "#f5b544";

export function TargetLeadReticle({ droneId }: { droneId: string }) {
  const batch = useVisionDetectionsStore((s) => s.batches[droneId]);
  const selected = useSelectedTargetStore((s) => s.selected);
  const setMarks = useCockpitMarksStore((s) => s.setMarks);
  const clearSource = useCockpitMarksStore((s) => s.clearSource);

  const historyRef = useRef<TrackSample[]>([]);
  const trackRef = useRef<number | null>(null);

  const here = selected && selected.droneId === droneId ? selected : null;
  const trackId = here?.trackId ?? null;

  useEffect(() => {
    // A new designated track starts a fresh history (never blend two tracks).
    if (trackRef.current !== trackId) {
      trackRef.current = trackId;
      historyRef.current = [];
    }

    // Only a tracked target on a fresh feed gets a lead.
    if (trackId == null || !batch) {
      clearSource(SOURCE);
      return;
    }
    const fresh = Date.now() - batch.receivedAt <= DETECTION_STALE_MS;
    const det = fresh
      ? batch.detections.find((d) => d.trackId === trackId && d.bbox)
      : undefined;
    if (!det?.bbox) {
      clearSource(SOURCE);
      return;
    }

    const bbox = det.bbox;
    const cx = bbox.x + bbox.width / 2;
    const cy = bbox.y + bbox.height / 2;
    historyRef.current = pushLeadSample(
      historyRef.current,
      { t: batch.receivedAt, cx, cy },
      LEAD_HISTORY_MS,
    );

    const lead = computeLead(
      historyRef.current,
      LEAD_MS,
      MIN_LEAD_SPEED_PX_PER_SEC,
    );
    if (!lead) {
      // Tracked but stationary (or too few samples) → no fabricated heading.
      clearSource(SOURCE);
      return;
    }

    const { width: w, height: h } = bbox;
    const marks: CockpitMark[] = [
      {
        id: `${SOURCE}:vec`,
        kind: "polyline",
        points: [
          [cx, cy],
          [lead.cx, lead.cy],
        ],
        color: LEAD_COLOR,
        width: 2,
      },
      {
        id: `${SOURCE}:reticle`,
        kind: "reticle",
        x: lead.cx - w / 2,
        y: lead.cy - h / 2,
        width: w,
        height: h,
        color: LEAD_COLOR,
      },
      {
        id: `${SOURCE}:dot`,
        kind: "point",
        x: lead.cx,
        y: lead.cy,
        radius: 3,
        color: LEAD_COLOR,
      },
    ];
    setMarks(SOURCE, marks);
  }, [batch, trackId, setMarks, clearSource]);

  // Drop the lead marks on unmount / drone switch so B never shows A's lead.
  useEffect(() => {
    return () => clearSource(SOURCE);
  }, [droneId, clearSource]);

  return null;
}
