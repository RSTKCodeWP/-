"use client";

/**
 * @module DisclaimerStep
 * @description Legal disclaimer step. Six-section scrollable copy plus an
 * accept checkbox. Cannot proceed until checked. On accept, persists the
 * disclaimer version so future loads skip the standalone gate.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useSettingsStore } from "@/stores/settings-store";
import { PRIMARY_CTA_CLASS, DISCLAIMER_VERSION } from "../constants";
import { StepDots } from "../parts/StepDots";
import { BackButton } from "./BackButton";
import { DisclaimerBody } from "./DisclaimerBody";

interface Props {
  checked: boolean;
  onChange: (next: boolean) => void;
  next: () => void;
  back: () => void;
  dotStep: number;
  totalSteps: number;
}

export function DisclaimerStep({ checked, onChange, next, back, dotStep, totalSteps }: Props) {
  const t = useTranslations("welcome");
  const setDisclaimerAccepted = useSettingsStore((s) => s.setDisclaimerAccepted);

  return (
    <>
      <BackButton onClick={back} />

      <div className="w-full max-w-2xl">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-1 text-center">
          {t("disclaimer.title")}
        </h2>
        <p className="text-xs text-text-tertiary mb-6 text-center">
          {t("disclaimer.subtitle")}
        </p>

        <DisclaimerBody />

        {/* Acceptance checkbox */}
        <label className="flex items-start gap-3 mb-6 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={checked}
            onChange={() => onChange(!checked)}
            className="mt-0.5 w-4 h-4 shrink-0 accent-accent-primary rounded-sm border-border-default bg-bg-tertiary"
          />
          <span className="text-xs text-text-primary leading-relaxed">
            {t("disclaimer.acceptCheckbox")}
          </span>
        </label>

        <button
          type="button"
          disabled={!checked}
          onClick={() => {
            setDisclaimerAccepted(DISCLAIMER_VERSION);
            next();
          }}
          className={`${PRIMARY_CTA_CLASS} block w-fit mx-auto ${!checked ? "opacity-50 cursor-not-allowed pointer-events-none" : ""}`}
        >
          {t("disclaimer.acceptButton")} →
        </button>

        <StepDots step={dotStep} total={totalSteps} />
      </div>
    </>
  );
}
