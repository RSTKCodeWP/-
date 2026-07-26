"use client";

/**
 * Mission adherence card — deviation + waypoint progress vs planned route.
 *
 * @module components/history/detail/tabs/overview/AdherenceCard
 */

import { MapPin } from "lucide-react";
import type { MissionAdherence } from "@/lib/types";
import { Row } from "./shared";

export function AdherenceCard({
  adherence,
  missionName,
}: {
  adherence: MissionAdherence;
  missionName?: string;
}) {
  const reachedPct =
    adherence.totalWaypoints > 0
      ? Math.round((adherence.waypointsReached / adherence.totalWaypoints) * 100)
      : 0;

  // Severity colour based on max cross-track error.
  const errColour =
    adherence.maxCrossTrackErrorM > 50
      ? "text-status-error"
      : adherence.maxCrossTrackErrorM > 20
        ? "text-status-warning"
        : "text-status-success";

  return (
    <div className="flex flex-col gap-2">
      {missionName && (
        <div className="flex items-center gap-1.5 text-[11px] text-text-secondary">
          <MapPin size={12} />
          <span className="text-text-primary">{missionName}</span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <Row
          label="Waypoints"
          value={`${adherence.waypointsReached}/${adherence.totalWaypoints} (${reachedPct}%)`}
        />
        <Row
          label="Max XTE"
          value={`${adherence.maxCrossTrackErrorM} m`}
        />
        <Row
          label="Mean XTE"
          value={`${adherence.meanCrossTrackErrorM} m`}
        />
        {adherence.deviationSegments && adherence.deviationSegments.length > 0 && (
          <Row
            label="Deviations"
            value={`${adherence.deviationSegments.length}`}
          />
        )}
      </div>
      {adherence.maxCrossTrackErrorM > 0 && (
        <div className={`text-[10px] font-mono ${errColour}`}>
          {adherence.maxCrossTrackErrorM > 50
            ? "Significant deviation from intended path"
            : adherence.maxCrossTrackErrorM > 20
              ? "Moderate deviation"
              : "Tracked the intended path closely"}
        </div>
      )}
    </div>
  );
}
