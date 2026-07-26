/**
 * @module LandingPointPicker
 * @description Reusable landing-point coordinate picker for the landing pattern
 * config sections. Provides numeric latitude/longitude inputs plus a
 * "Use map center" button that reads the current planner map center.
 * @license GPL-3.0-only
 */
"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { usePlannerStore } from "@/stores/planner-store";
import { Plane, Crosshair } from "lucide-react";

interface LandingPointPickerProps {
  /** Current landing point as [lat, lon], or undefined when not yet set. */
  landingPoint: [number, number] | undefined;
  /** Called with the next [lat, lon] whenever either coordinate changes. */
  onChange: (point: [number, number]) => void;
}

export function LandingPointPicker({ landingPoint, onChange }: LandingPointPickerProps) {
  const t = useTranslations("planner");

  const lat = landingPoint?.[0];
  const lon = landingPoint?.[1];

  const setLat = (value: string) => {
    const v = parseFloat(value);
    onChange([Number.isFinite(v) ? v : 0, lon ?? 0]);
  };
  const setLon = (value: string) => {
    const v = parseFloat(value);
    onChange([lat ?? 0, Number.isFinite(v) ? v : 0]);
  };
  const useMapCenter = () => {
    const center = usePlannerStore.getState().mapCenter;
    onChange([center[0], center[1]]);
  };

  return (
    <>
      <div className="flex items-center gap-1.5 text-[10px] font-mono text-text-tertiary">
        <Plane size={12} />
        <span>
          {landingPoint
            ? `${t("landingPoint")}: ${lat!.toFixed(5)}, ${lon!.toFixed(5)}`
            : t("setLandingPoint")}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Input
          label={t("lat")}
          type="number"
          value={lat !== undefined ? String(lat) : ""}
          placeholder="—"
          onChange={(e) => setLat(e.target.value)}
        />
        <Input
          label={t("lon")}
          type="number"
          value={lon !== undefined ? String(lon) : ""}
          placeholder="—"
          onChange={(e) => setLon(e.target.value)}
        />
      </div>
      <button
        onClick={useMapCenter}
        className="flex items-center justify-center gap-2 py-1.5 text-xs font-mono
          text-accent-primary border border-accent-primary/30 hover:bg-accent-primary/10
          transition-colors cursor-pointer"
      >
        <Crosshair size={12} />
        {t("useMapCenter")}
      </button>
    </>
  );
}
