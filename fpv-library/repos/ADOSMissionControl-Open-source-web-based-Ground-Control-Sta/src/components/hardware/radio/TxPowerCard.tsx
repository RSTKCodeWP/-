"use client";

/**
 * @module hardware/radio/TxPowerCard
 * @description TX power slider section. The slider itself lives in the
 * shared TxPowerSlider component; this card just wraps it with the
 * heading and per-driver hard-cap label.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { TxPowerSlider } from "@/components/hardware/TxPowerSlider";
import type { SetTxPowerResult } from "@/lib/api/ground-station/types";

export interface TxPowerCardProps {
  txPowerDbm: number | null;
  txPowerMaxDbm: number;
  hostname: string | null;
  onApply: (dbm: number) => Promise<SetTxPowerResult>;
}

export function TxPowerCard({
  txPowerDbm,
  txPowerMaxDbm,
  hostname,
  onApply,
}: TxPowerCardProps) {
  const t = useTranslations("hardware.radio");
  const initialSliderValue = txPowerDbm ?? 5;
  const safeMax = Math.max(1, txPowerMaxDbm);
  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <h3 className="mb-1 text-sm font-semibold text-text-primary">
        {t("txPower")}
      </h3>
      <p className="mb-4 text-xs text-text-tertiary">
        {t("txPowerHardCap", { max: safeMax })}
      </p>
      <TxPowerSlider
        currentDbm={txPowerDbm}
        maxDbm={safeMax}
        initialValue={initialSliderValue}
        confirmHostname={hostname}
        onApply={onApply}
      />
    </section>
  );
}
