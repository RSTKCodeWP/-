"use client";

/**
 * @module hardware/radio/WfbTuningCard
 * @description Operator radio-link tuning: link preset, FEC ratio, MCS rate,
 * and the adaptive-FEC toggle. Mirrors the TxPowerCard write pattern (apply →
 * optimistic toast → surface agent warnings). The control values reflect the
 * data plane's LIVE trio from the per-drone radio snapshot, so an automatic
 * adaptive step or a manual change shows here on the next heartbeat.
 * @license GPL-3.0-only
 */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { SlidersHorizontal } from "lucide-react";
import { Select } from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import type { LinkPreset } from "@/lib/api/ground-station/wfb";
import type { VideoConfigResponse } from "@/lib/api/ground-station/types";

// FEC ratios offered in the picker, most-protected first. Mirrors the agent's
// preset trios + adaptive ladder rungs; the operator can still land on a ratio
// outside this list via calibration or a preset (the picker then shows blank).
const FEC_RATIOS: ReadonlyArray<[number, number]> = [
  [8, 16],
  [8, 14],
  [8, 12],
  [8, 10],
  [4, 12],
];

// Preset -> (mcs, fecK, fecN). Mirrors the agent link_preset_trio table so the
// picker can show which preset the live trio currently matches.
const PRESET_TRIOS: Record<LinkPreset, [number, number, number]> = {
  conservative: [1, 8, 12],
  balanced: [3, 8, 12],
  aggressive: [5, 8, 10],
};

// MCS at or above this needs strong signal; gate it behind a confirm so a tap
// can't silently drop a marginal link.
const MCS_CONFIRM_FLOOR = 5;

export interface WfbTuningCardProps {
  fecK: number | null;
  fecN: number | null;
  mcsIndex: number | null;
  adaptiveBitrateEnabled: boolean | null;
  recommendedTierName: string | null;
  onApplyPreset: (preset: LinkPreset) => Promise<VideoConfigResponse>;
  onApplyFec: (fecK: number, fecN: number) => Promise<VideoConfigResponse>;
  onApplyMcs: (mcs: number) => Promise<VideoConfigResponse>;
  onToggleAdaptive: (enabled: boolean) => Promise<VideoConfigResponse>;
  /** Opens the calibration wizard. Undefined renders the button disabled. */
  onCalibrate?: () => void;
}

function matchPreset(
  mcs: number | null,
  k: number | null,
  n: number | null,
): LinkPreset | "custom" {
  for (const [name, trio] of Object.entries(PRESET_TRIOS) as [
    LinkPreset,
    [number, number, number],
  ][]) {
    if (trio[0] === mcs && trio[1] === k && trio[2] === n) return name;
  }
  return "custom";
}

export function WfbTuningCard({
  fecK,
  fecN,
  mcsIndex,
  adaptiveBitrateEnabled,
  recommendedTierName,
  onApplyPreset,
  onApplyFec,
  onApplyMcs,
  onToggleAdaptive,
  onCalibrate,
}: WfbTuningCardProps) {
  const t = useTranslations("hardware.radio");
  const tCommon = useTranslations("common");
  const { toast } = useToast();

  // Which control is mid-apply (disables the row + shows the parent is busy).
  const [busy, setBusy] = useState<string | null>(null);
  // A pending high-MCS value awaiting the confirm dialog.
  const [pendingMcs, setPendingMcs] = useState<number | null>(null);

  const adaptiveOn = adaptiveBitrateEnabled ?? false;
  const activePreset = matchPreset(mcsIndex, fecK, fecN);
  const presetValue = activePreset === "custom" ? "" : activePreset;
  const fecValue = fecK != null && fecN != null ? `${fecK}/${fecN}` : "";

  async function run(
    key: string,
    fn: () => Promise<VideoConfigResponse>,
  ): Promise<void> {
    setBusy(key);
    try {
      const res = await fn();
      const warnings = res.warnings ?? [];
      if (warnings.length > 0) {
        toast(`${t("tuning.applyPartial")}: ${warnings.join(", ")}`, "warning");
      } else {
        toast(t("applied"), "success");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "apply failed";
      toast(`${t("applyFailed")}: ${msg}`, "error");
    } finally {
      setBusy(null);
    }
  }

  const presetOptions = [
    { value: "conservative", label: t("tuning.presetConservative") },
    { value: "balanced", label: t("tuning.presetBalanced") },
    { value: "aggressive", label: t("tuning.presetAggressive") },
    { value: "custom", label: t("tuning.presetCustom"), disabled: true },
  ];

  const fecOptions = FEC_RATIOS.map(([k, n]) => ({
    value: `${k}/${n}`,
    label: t("tuning.fecOption", {
      k,
      n,
      pct: Math.round(((n - k) / k) * 100),
    }),
  }));

  const mcsOptions = Array.from({ length: 8 }, (_, i) => ({
    value: String(i),
    label: String(i),
  }));

  const disabled = busy != null;

  const onPresetChange = (value: string) => {
    if (value === "custom" || value === presetValue) return;
    void run("preset", () => onApplyPreset(value as LinkPreset));
  };

  const onFecChange = (value: string) => {
    if (value === fecValue) return;
    const [k, n] = value.split("/").map(Number);
    if (!Number.isFinite(k) || !Number.isFinite(n)) return;
    void run("fec", () => onApplyFec(k, n));
  };

  const onMcsChange = (value: string) => {
    const mcs = Number(value);
    if (!Number.isFinite(mcs) || mcs === mcsIndex) return;
    if (mcs >= MCS_CONFIRM_FLOOR) {
      setPendingMcs(mcs);
      return;
    }
    void run("mcs", () => onApplyMcs(mcs));
  };

  const confirmMcs = () => {
    const mcs = pendingMcs;
    setPendingMcs(null);
    if (mcs != null) void run("mcs", () => onApplyMcs(mcs));
  };

  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="mb-1 flex items-center gap-2">
        <SlidersHorizontal size={14} className="text-text-tertiary" />
        <h3 className="text-sm font-semibold text-text-primary">
          {t("tuning.title")}
        </h3>
      </div>
      <p className="mb-4 text-xs text-text-tertiary">{t("tuning.description")}</p>

      <div className="flex flex-col gap-4">
        <div>
          <Select
            label={t("tuning.preset")}
            options={presetOptions}
            value={presetValue}
            placeholder={t("tuning.presetCustom")}
            onChange={onPresetChange}
            disabled={disabled}
          />
        </div>

        <div>
          <Select
            label={t("tuning.fec")}
            options={fecOptions}
            value={fecValue}
            placeholder="—"
            onChange={onFecChange}
            disabled={disabled}
          />
          <p className="mt-1 text-xs text-text-tertiary">{t("tuning.fecHint")}</p>
        </div>

        <div>
          <Select
            label={t("tuning.mcs")}
            options={mcsOptions}
            value={mcsIndex != null ? String(mcsIndex) : ""}
            placeholder="—"
            onChange={onMcsChange}
            disabled={disabled}
          />
          <p className="mt-1 text-xs text-text-tertiary">{t("tuning.mcsHint")}</p>
        </div>

        <div>
          <Toggle
            label={t("tuning.adaptive")}
            checked={adaptiveOn}
            onChange={(next) =>
              void run("adaptive", () => onToggleAdaptive(next))
            }
            disabled={disabled}
          />
          <p className="mt-1 text-xs text-text-tertiary">
            {adaptiveOn && recommendedTierName
              ? t("tuning.adaptiveActiveTier", { tier: recommendedTierName })
              : t("tuning.adaptiveHint")}
          </p>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-border-default pt-3">
          <span className="text-xs text-text-tertiary">
            {onCalibrate ? t("tuning.calibrateHint") : t("tuning.calibrateComingSoon")}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={onCalibrate}
            disabled={!onCalibrate || disabled}
            title={onCalibrate ? undefined : t("tuning.calibrateComingSoon")}
          >
            {t("tuning.calibrate")}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={pendingMcs != null}
        title={t("tuning.mcsConfirmTitle")}
        message={t("tuning.mcsConfirmBody", { mcs: pendingMcs ?? "" })}
        confirmLabel={t("applyButton")}
        cancelLabel={tCommon("cancel")}
        variant="primary"
        onConfirm={confirmMcs}
        onCancel={() => setPendingMcs(null)}
      />
    </section>
  );
}
