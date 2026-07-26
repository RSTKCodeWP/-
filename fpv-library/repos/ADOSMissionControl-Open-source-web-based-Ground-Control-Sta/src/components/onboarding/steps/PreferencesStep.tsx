"use client";

/**
 * @module PreferencesStep
 * @description Jurisdiction, units, demo mode, audio alerts, and location
 * permission. Local form state lives in the parent so the user can move
 * back and forth without losing entries.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/select";
import { JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction";
import type { UnitSystem } from "@/stores/settings-store";
import type { GeoPermission } from "@/stores/gcs-location-store";
import { JURISDICTION_OPTIONS, PRIMARY_CTA_CLASS } from "../constants";
import { Toggle } from "../parts/Toggle";
import { StepDots } from "../parts/StepDots";
import { BackButton } from "./BackButton";

interface Props {
  jurisdiction: Jurisdiction | "";
  units: UnitSystem;
  demoMode: boolean;
  audioEnabled: boolean;
  locationEnabled: boolean;
  locationPermission: GeoPermission;
  locationChecking: boolean;
  isLocationSupported: boolean;
  setJurisdiction: (j: Jurisdiction | "") => void;
  setUnits: (u: UnitSystem) => void;
  setDemoMode: (v: boolean) => void;
  setAudioEnabled: (v: boolean) => void;
  onLocationToggle: () => void;
  next: () => void;
  back: () => void;
  dotStep: number;
  totalSteps: number;
}

export function PreferencesStep({
  jurisdiction,
  units,
  demoMode,
  audioEnabled,
  locationEnabled,
  locationPermission,
  locationChecking,
  isLocationSupported,
  setJurisdiction,
  setUnits,
  setDemoMode,
  setAudioEnabled,
  onLocationToggle,
  next,
  back,
  dotStep,
  totalSteps,
}: Props) {
  const t = useTranslations("welcome");
  const tCommon = useTranslations("common");

  return (
    <>
      <BackButton onClick={back} />

      <div className="w-full max-w-lg">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-6 text-center">
          {t("preferences.title")}
        </h2>

        <div className="space-y-4">
          {/* Jurisdiction */}
          <div>
            <Select
              label={t("preferences.jurisdiction")}
              value={jurisdiction}
              onChange={(v) => {
                const j = v as Jurisdiction | "";
                setJurisdiction(j);
                if (j) setUnits(JURISDICTIONS[j].defaultUnits);
              }}
              placeholder={`${t("preferences.jurisdictionOptional")}`}
              options={JURISDICTION_OPTIONS}
            />
          </div>

          {/* Units */}
          <div>
            <Select
              label={t("preferences.units")}
              value={units}
              onChange={(v) => setUnits(v as UnitSystem)}
              options={[
                { value: "metric", label: t("preferences.metric") },
                { value: "imperial", label: t("preferences.imperial") },
              ]}
            />
          </div>

          {/* Demo mode */}
          <div className="flex items-center justify-between pt-3 border-t border-border-default">
            <div>
              <span className="text-sm text-text-primary">{t("preferences.demoMode")}</span>
              <p className="text-[10px] text-text-tertiary mt-0.5">{t("preferences.demoModeDescription")}</p>
            </div>
            <Toggle checked={demoMode} onChange={() => setDemoMode(!demoMode)} />
          </div>

          {/* Audio */}
          <div className="flex items-center justify-between pt-3 border-t border-border-default">
            <div>
              <span className="text-sm text-text-primary">{t("preferences.audioAlerts")}</span>
              <p className="text-[10px] text-text-tertiary mt-0.5">{t("preferences.audioAlertsDescription")}</p>
            </div>
            <Toggle checked={audioEnabled} onChange={() => setAudioEnabled(!audioEnabled)} />
          </div>

          {/* Location */}
          <div className="flex items-center justify-between pt-3 border-t border-border-default">
            <div className="pe-4">
              <span className="text-sm text-text-primary">{t("preferences.yourPosition")}</span>
              <p className="text-[10px] text-text-tertiary mt-0.5">{t("preferences.yourPositionDescription")}</p>
              {locationPermission === "granted" && locationEnabled && (
                <p className="text-[10px] text-status-success mt-0.5">{t("preferences.locationGranted")}</p>
              )}
              {locationPermission === "denied" && (
                <p className="text-[10px] text-status-warning mt-0.5">{t("preferences.locationDenied")}</p>
              )}
            </div>
            <Toggle
              checked={locationEnabled}
              onChange={onLocationToggle}
              disabled={locationChecking || !isLocationSupported}
            />
          </div>
        </div>

        <button
          type="button"
          onClick={next}
          className={`${PRIMARY_CTA_CLASS} mt-8 block w-fit mx-auto`}
        >
          {tCommon("continue")} →
        </button>

        <StepDots step={dotStep} total={totalSteps} />
      </div>
    </>
  );
}
