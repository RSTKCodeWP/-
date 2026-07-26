/**
 * @module GsdSpeedControls
 * @description GSD-first survey helpers. Sets the flight altitude from a target
 * ground sample distance, and warns when the survey speed would smear the image
 * beyond a pixel of motion blur for the configured exposure time.
 * @license GPL-3.0-only
 */
"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { usePatternStore } from "@/stores/pattern-store";
import type { CameraProfile } from "@/lib/patterns/gsd-calculator";
import {
  computeGSD,
  computeLineSpacing,
  computeTriggerDistance,
} from "@/lib/patterns/gsd-calculator";
import {
  solveAltitudeForGSD,
  maxSafeGroundSpeed,
  motionBlurPixels,
} from "@/lib/patterns/gsd-solver";

interface GsdSpeedControlsProps {
  camera: CameraProfile | undefined;
  /** Target side overlap percentage, used to recompute line spacing. */
  sidelapPct: number;
  /** Target front overlap percentage, used to recompute trigger distance. */
  frontlapPct: number;
}

export function GsdSpeedControls({ camera, sidelapPct, frontlapPct }: GsdSpeedControlsProps) {
  const t = useTranslations("survey");
  const surveyConfig = usePatternStore((s) => s.surveyConfig);
  const updateSurveyConfig = usePatternStore((s) => s.updateSurveyConfig);

  const [targetGsd, setTargetGsd] = useState("");
  const [exposure, setExposure] = useState("0.002");

  const altitude = surveyConfig.altitude ?? 50;
  const speed = surveyConfig.speed ?? 5;

  const handleTargetGsd = useCallback(
    (raw: string) => {
      setTargetGsd(raw);
      const gsd = parseFloat(raw);
      if (!camera || !(gsd > 0)) return;
      const alt = Math.round(solveAltitudeForGSD(gsd, camera));
      if (alt <= 0) return;
      updateSurveyConfig({
        altitude: alt,
        lineSpacing: Math.round(computeLineSpacing(alt, camera, sidelapPct / 100) * 10) / 10,
        cameraTriggerDistance:
          Math.round(computeTriggerDistance(alt, camera, frontlapPct / 100) * 10) / 10,
      } as Partial<typeof surveyConfig>);
    },
    [camera, sidelapPct, frontlapPct, updateSurveyConfig],
  );

  const blur = useMemo(() => {
    if (!camera) return null;
    const gsdCmPerPx =
      computeGSD(altitude, camera.focalLength, camera.sensorWidth, camera.imageWidth) * 100;
    const exp = parseFloat(exposure) || 0;
    const maxSpeed = maxSafeGroundSpeed(gsdCmPerPx, exp);
    if (maxSpeed <= 0) return null;
    const unsafe = speed > maxSpeed;
    return { maxSpeed, unsafe, px: unsafe ? motionBlurPixels(speed, exp, gsdCmPerPx) : 0 };
  }, [camera, altitude, exposure, speed]);

  if (!camera) return null;

  return (
    <div className="flex flex-col gap-2">
      <Input
        label={t("targetGsd")}
        type="number"
        unit="cm/px"
        min={0.1}
        step={0.1}
        placeholder="e.g. 2"
        value={targetGsd}
        onChange={(e) => handleTargetGsd(e.target.value)}
      />
      <Input
        label={t("exposureTime")}
        type="number"
        unit="s"
        min={0}
        step={0.001}
        placeholder="0.002"
        value={exposure}
        onChange={(e) => setExposure(e.target.value)}
      />
      {blur && (
        <div className="flex flex-col gap-0.5">
          <span className="text-[9px] font-mono text-text-tertiary">
            {t("maxSafeSpeed")}: {blur.maxSpeed.toFixed(1)} m/s
          </span>
          {blur.unsafe && (
            <span className="text-[9px] font-mono text-status-warning">
              {t("motionBlur", { blur: blur.px.toFixed(1), max: blur.maxSpeed.toFixed(1) })}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
