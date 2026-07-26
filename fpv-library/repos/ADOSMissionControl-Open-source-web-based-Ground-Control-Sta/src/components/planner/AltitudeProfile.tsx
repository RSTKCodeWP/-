/**
 * @module AltitudeProfile
 * @description Collapsible altitude profile chart shown below the map.
 * Plots waypoint altitude vs cumulative ground distance using recharts.
 * Waypoint dots are clickable to select/expand in the list panel.
 * @license GPL-3.0-only
 */
"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Dot } from "recharts";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { Waypoint } from "@/lib/types";
import { cumulativeGroundDistances } from "@/lib/altitude-profile";
import { MAP_COLORS } from "@/lib/map-constants";
import { useSettingsStore } from "@/stores/settings-store";
import { formatDistance, formatAltitude } from "@/lib/units/format";

/** Data point for the altitude profile chart. */
interface AltitudeDataPoint {
  id: string;
  distance: number;
  alt: number;
  label: string;
}

interface AltitudeProfileProps {
  waypoints: Waypoint[];
  collapsed: boolean;
  onToggle: () => void;
  selectedWaypointId: string | null;
  onSelectWaypoint: (id: string) => void;
}

export function AltitudeProfile({
  waypoints,
  collapsed,
  onToggle,
  selectedWaypointId,
  onSelectWaypoint,
}: AltitudeProfileProps) {
  const t = useTranslations("planner");
  const units = useSettingsStore((s) => s.units);
  const data: AltitudeDataPoint[] = useMemo(() => {
    const distances = cumulativeGroundDistances(waypoints);
    return waypoints.map((wp, i) => {
      const cumDist = distances[i];
      return {
        id: wp.id,
        distance: Math.round(cumDist),
        alt: wp.alt,
        label: `WP${i + 1}`,
      };
    });
  }, [waypoints]);

  if (waypoints.length === 0) return null;

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[999]">
      <div className="mx-3 mb-3 bg-bg-secondary/95 border border-border-default">
        {/* Header */}
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-between px-3 py-1.5 cursor-pointer hover:bg-bg-tertiary transition-colors"
        >
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            {t("altitudeProfile")}
          </span>
          {collapsed ? <ChevronUp size={12} className="text-text-tertiary" /> : <ChevronDown size={12} className="text-text-tertiary" />}
        </button>

        {/* Chart */}
        {!collapsed && (
          <div className="h-[100px] px-1 pb-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="altGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={MAP_COLORS.accentPrimary} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={MAP_COLORS.accentPrimary} stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="distance"
                  tick={{ fill: "var(--alt-text-tertiary)", fontSize: 9, fontFamily: "JetBrains Mono" }}
                  axisLine={{ stroke: "var(--alt-border-default)" }}
                  tickLine={false}
                  tickFormatter={(v) => formatDistance(Number(v), units)}
                />
                <YAxis
                  tick={{ fill: "var(--alt-text-tertiary)", fontSize: 9, fontFamily: "JetBrains Mono" }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                  tickFormatter={(v) => formatAltitude(Number(v), units)}
                />
                <Area
                  type="monotone"
                  dataKey="alt"
                  stroke={MAP_COLORS.accentPrimary}
                  strokeWidth={1.5}
                  fill="url(#altGrad)"
                  dot={(props) => {
                    const { cx, cy, payload } = props as { cx: number; cy: number; payload: AltitudeDataPoint };
                    const isSelected = payload.id === selectedWaypointId;
                    return (
                      <Dot
                        key={payload.id}
                        cx={cx}
                        cy={cy}
                        r={isSelected ? 5 : 3}
                        fill={isSelected ? MAP_COLORS.accentPrimary : MAP_COLORS.foreground}
                        stroke={MAP_COLORS.accentPrimary}
                        strokeWidth={1.5}
                        style={{ cursor: "pointer" }}
                        onClick={() => onSelectWaypoint(payload.id)}
                      />
                    );
                  }}
                  activeDot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
