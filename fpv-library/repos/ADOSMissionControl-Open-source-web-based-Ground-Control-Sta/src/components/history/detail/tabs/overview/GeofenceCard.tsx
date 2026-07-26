"use client";

/**
 * Geofence breach summary card for flight history.
 *
 * @module components/history/detail/tabs/overview/GeofenceCard
 */

import { AlertTriangle, Hexagon } from "lucide-react";
import type { GeofenceBreach } from "@/lib/types";

const BREACH_LABELS: Record<GeofenceBreach["type"], string> = {
  polygon_outside: "Outside polygon",
  polygon_inside: "Inside exclusion polygon",
  circle_outside: "Outside circle",
  circle_inside: "Inside exclusion circle",
  max_altitude: "Above max altitude",
  min_altitude: "Below min altitude",
};

export function GeofenceCard({ breaches }: { breaches: GeofenceBreach[] }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-[11px] text-status-error">
        <AlertTriangle size={12} />
        <span className="uppercase tracking-wider font-semibold">
          {breaches.length} breach{breaches.length === 1 ? "" : "es"} detected
        </span>
      </div>
      <ul className="flex flex-col gap-1.5">
        {breaches.map((b, i) => (
          <li
            key={`${b.zoneId}-${b.type}-${i}`}
            className="flex flex-col gap-0.5 border-l-2 border-status-error pl-2 py-0.5"
          >
            <div className="flex items-center justify-between gap-2 text-[11px]">
              <span className="inline-flex items-center gap-1.5 text-text-primary">
                <Hexagon size={10} className="text-status-error" />
                {BREACH_LABELS[b.type]}
              </span>
              {b.maxBreachDistanceM !== undefined && b.maxBreachDistanceM > 0 && (
                <span className="font-mono text-status-error">
                  +{b.maxBreachDistanceM} m
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[10px] text-text-tertiary font-mono">
              <span>zone: {b.zoneId}</span>
              <span>
                pts {b.startIdx}–{b.endIdx}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
