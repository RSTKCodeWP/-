/**
 * @module SimulationStatsGrid
 * @description Mission overview stats grid plus altitude and terrain profile
 * sections for the simulation panel. Pure presentational; receives all data
 * and collapsible state from the parent.
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { Mountain, ChevronDown } from "lucide-react";
import type { Waypoint } from "@/lib/types";
import type { FlightPlan } from "@/lib/simulation-utils";
import { formatEta } from "@/lib/simulation-utils";
import { cn } from "@/lib/utils";
import { AltitudeProfile } from "./AltitudeProfile";
import { TerrainProfileChart } from "@/components/planner/TerrainProfileChart";

interface SimulationStatsGridProps {
  waypoints: Waypoint[];
  flightPlan: FlightPlan;
  totalDuration: number;
  speed: number;
  heading: number;
  progressPct: number;
  terrainExpanded: boolean;
  onToggleTerrain: () => void;
}

export function SimulationStatsGrid({
  waypoints,
  flightPlan,
  totalDuration,
  speed,
  heading,
  progressPct,
  terrainExpanded,
  onToggleTerrain,
}: SimulationStatsGridProps) {
  const t = useTranslations("simulate");

  return (
    <>
      {/* Mission overview stats grid (2x3) */}
      <div className="px-3 py-2 border-b border-border-default grid grid-cols-3 gap-2">
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("duration")}</span>
          <p className="text-xs font-mono text-text-primary">{formatEta(totalDuration)}</p>
        </div>
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("distance")}</span>
          <p className="text-xs font-mono text-text-primary">
            {flightPlan.totalDistance >= 1000
              ? `${(flightPlan.totalDistance / 1000).toFixed(2)} km`
              : `${Math.round(flightPlan.totalDistance)} m`}
          </p>
        </div>
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("speed")}</span>
          <p className="text-xs font-mono text-text-primary">{speed.toFixed(1)} m/s</p>
        </div>
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("heading")}</span>
          <p className="text-xs font-mono text-text-primary">{Math.round(heading)}&deg;</p>
        </div>
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("waypoints")}</span>
          <p className="text-xs font-mono text-text-primary">{waypoints.length}</p>
        </div>
        <div>
          <span className="text-[10px] font-mono text-text-tertiary">{t("progress")}</span>
          <div className="flex items-center gap-1.5">
            <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-accent-primary rounded-full transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-text-primary">{Math.round(progressPct)}%</span>
          </div>
        </div>
      </div>

      {/* Altitude profile */}
      <div className="px-3 py-2 border-b border-border-default">
        <h3 className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider mb-1">
          {t("altitudeProfile")}
        </h3>
        <AltitudeProfile waypoints={waypoints} flightPlan={flightPlan} />
      </div>

      {/* Terrain profile (collapsible) */}
      {waypoints.length >= 2 && (
        <div className="border-b border-border-default">
          <button
            onClick={onToggleTerrain}
            className="w-full flex items-center gap-1.5 px-3 py-2 cursor-pointer hover:bg-bg-tertiary transition-colors"
          >
            <Mountain size={12} className="text-text-tertiary" />
            <span className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider flex-1 text-left">
              {t("terrainProfile")}
            </span>
            <ChevronDown
              size={12}
              className={cn(
                "text-text-tertiary transition-transform",
                terrainExpanded && "rotate-180"
              )}
            />
          </button>
          {terrainExpanded && (
            <TerrainProfileChart waypoints={waypoints} />
          )}
        </div>
      )}
    </>
  );
}
