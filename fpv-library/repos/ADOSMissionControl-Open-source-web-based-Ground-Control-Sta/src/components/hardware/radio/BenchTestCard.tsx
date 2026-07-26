"use client";

/**
 * @module hardware/radio/BenchTestCard
 * @description Bench Test Mode toggle card. Stub today; the toggle is
 * wired but disabled pending the bench-mode supervisor on the agent.
 * @license GPL-3.0-only
 */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export function BenchTestCard() {
  const t = useTranslations("hardware.radio");
  const [benchMode, setBenchMode] = useState(false);
  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-text-primary">
            {t("benchTestMode")}
          </h3>
          <p className="text-xs text-text-tertiary">
            {t("airSide")} / {t("groundSide")}
          </p>
        </div>
        <Button
          variant={benchMode ? "primary" : "secondary"}
          size="sm"
          onClick={() => setBenchMode((v) => !v)}
          disabled
        >
          {t("benchTestMode")}
        </Button>
      </div>
    </section>
  );
}
