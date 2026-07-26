/**
 * @module EnergyCard
 * @description Compact planner review card estimating a mission's energy budget:
 * total watt-hours, flight time, and how many mid-mission battery swaps the plan
 * implies. Distance comes from the real waypoint path (haversine sum); power and
 * pack capacity are first-order defaults documented below, so the card labels
 * itself an estimate and no more precision is implied than the inputs justify.
 *
 * When the path has no length yet (fewer than two waypoints) every figure shows
 * an honest em-dash rather than a fabricated number.
 * @license GPL-3.0-only
 */
"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Zap, Clock, BatteryCharging } from "lucide-react";
import { totalPathDistance } from "@/lib/telemetry-utils";
import { estimateEnergyWh, segmentByBattery } from "@/lib/energy-model";

/**
 * First-order planning defaults for a ~2 kg class multirotor carrying the ADOS
 * companion stack. These are deliberate stand-ins for a measured power curve,
 * not calibrated telemetry; the card is labelled an estimate accordingly.
 */
const DEFAULT_CRUISE_MPS = 8; // typical small-multirotor forward cruise
const HOVER_WATTS = 220; // hover-in-place draw estimate
const CRUISE_WATTS = 180; // forward-cruise draw estimate
const BATTERY_WH = 185; // rated pack energy estimate (6S Li-ion class)
const RESERVE_FRACTION = 0.2; // landing reserve held back per pack

const PLACEHOLDER = "—";

interface EnergyCardProps {
  /** Ordered mission waypoints; only lat/lon are read for the path length. */
  waypoints: { lat: number; lon: number }[];
  /** Cruise speed in m/s; falls back to a default when non-positive. */
  cruiseSpeedMps?: number;
}

/** "42m" under an hour, "1h 12m" at or above it. */
function fmtMinutes(minutes: number): string {
  const total = Math.round(minutes);
  if (total < 60) return `${total}m`;
  return `${Math.floor(total / 60)}h ${total % 60}m`;
}

export function EnergyCard({ waypoints, cruiseSpeedMps }: EnergyCardProps) {
  const t = useTranslations("planner.energy");
  const cruise =
    cruiseSpeedMps && cruiseSpeedMps > 0 ? cruiseSpeedMps : DEFAULT_CRUISE_MPS;

  const est = useMemo(() => {
    const distanceM = totalPathDistance(waypoints);
    if (distanceM <= 0) return null;
    const energy = estimateEnergyWh({
      distanceM,
      cruiseSpeedMps: cruise,
      hoverWatts: HOVER_WATTS,
      cruiseWatts: CRUISE_WATTS,
    });
    const batt = segmentByBattery(energy.totalWh, BATTERY_WH, RESERVE_FRACTION);
    return { energy, batt };
  }, [waypoints, cruise]);

  const swapsValue =
    est && Number.isFinite(est.batt.swaps) ? String(est.batt.swaps) : PLACEHOLDER;

  const rows: { key: string; label: string; icon: typeof Zap; value: string }[] = [
    {
      key: "energy",
      label: t("required"),
      icon: Zap,
      value: est ? `${Math.round(est.energy.totalWh)} Wh` : PLACEHOLDER,
    },
    {
      key: "time",
      label: t("flightTime"),
      icon: Clock,
      value: est ? fmtMinutes(est.energy.flightMinutes) : PLACEHOLDER,
    },
    {
      key: "swaps",
      label: t("swaps"),
      icon: BatteryCharging,
      value: swapsValue,
    },
  ];

  return (
    <div className="bg-bg-secondary border border-border-default rounded-md p-3 text-xs">
      <div className="flex items-center gap-2 mb-2">
        <Zap className="w-3.5 h-3.5 text-accent-primary" />
        <span className="font-medium text-text-primary">{t("title")}</span>
        <span className="ml-auto text-[10px] uppercase tracking-wide text-text-tertiary">
          {t("estimate")}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {rows.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.key} className="flex items-center gap-2">
              <Icon className="w-3.5 h-3.5 text-text-secondary shrink-0" />
              <span className="text-text-secondary">{r.label}</span>
              <span className="ml-auto font-mono text-text-primary tabular-nums">
                {r.value}
              </span>
            </div>
          );
        })}
      </div>

      <p className="mt-2 text-[10px] leading-snug text-text-tertiary">{t("note")}</p>
    </div>
  );
}
