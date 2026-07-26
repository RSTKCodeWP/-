/**
 * @module FixedWingLandingConfigSection
 * @description Fixed-wing landing pattern configuration UI.
 * Exposes the landing point, approach geometry, glide slope, and speed for the
 * straight-in approach and landing sequence.
 * @license GPL-3.0-only
 */
"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { usePatternStore } from "@/stores/pattern-store";
import { LandingPointPicker } from "./LandingPointPicker";

export function FixedWingLandingConfig() {
  const t = useTranslations("planner");
  const config = usePatternStore((s) => s.fixedWingLandingConfig);
  const update = usePatternStore((s) => s.updateFixedWingLandingConfig);
  return (
    <>
      <LandingPointPicker
        landingPoint={config.landingPoint}
        onChange={(landingPoint) => update({ landingPoint })}
      />
      <Input label={t("approachHeading")} type="number" unit="deg" placeholder="-1 = auto"
        value={String(config.approachHeading ?? -1)}
        onChange={(e) => {
          const v = parseFloat(e.target.value);
          update({ approachHeading: Number.isFinite(v) ? v : -1 });
        }} />
      <Input label={t("approachDistance")} type="number" unit="m" value={String(config.approachDistance ?? 400)}
        onChange={(e) => update({ approachDistance: parseFloat(e.target.value) || 400 })} />
      <Input label={t("glideSlopeAngle")} type="number" unit="deg" value={String(config.glideSlopeAngle ?? 5)}
        onChange={(e) => update({ glideSlopeAngle: parseFloat(e.target.value) || 5 })} />
      <div className="grid grid-cols-2 gap-2">
        <Input label={t("loiterAltitude")} type="number" unit="m" value={String(config.loiterAltitude ?? 60)}
          onChange={(e) => update({ loiterAltitude: parseFloat(e.target.value) || 60 })} />
        <Input label={t("speedMs")} type="number" unit="m/s" value={String(config.speed ?? 15)}
          onChange={(e) => update({ speed: parseFloat(e.target.value) || 15 })} />
      </div>
    </>
  );
}
