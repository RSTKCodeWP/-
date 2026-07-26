"use client";

/**
 * @module fc/firmware/agent-stages/WebFlashCard
 * @description WebUSB flash card. Composes the connection panel,
 * the progress region, the confirmation pill, and the Flash button.
 * @license GPL-3.0-only
 */

import { Usb, X, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/select";
import type { AdosAgentWebFlashInstall } from "@/lib/protocol/firmware/ados-agent-manifest";
import type { FlashProgress } from "@/lib/protocol/firmware/types";
import type { UsbDeviceInfo } from "@/lib/usb-device-manager";
import { FirmwareFlashProgress } from "../FirmwareFlashProgress";
import { RockchipConnectionPanel } from "./RockchipConnectionPanel";

export interface WebFlashCardProps {
  webFlashInstall: AdosAgentWebFlashInstall;
  devices: UsbDeviceInfo[];
  usbSupported: boolean;
  isFlashing: boolean;
  allChecked: boolean;
  statusMessage: string;
  progress: FlashProgress | null;
  confirming: boolean;
  confirmDeviceLabel: string;
  onSelectConfirmDevice: (label: string) => void;
  onScanForBoard: () => void;
  onFlash: () => void;
  onCancelConfirm: () => void;
  onConfirmFlash: () => void;
  onAbort: () => void;
}

export function WebFlashCard({
  webFlashInstall,
  devices,
  usbSupported,
  isFlashing,
  allChecked,
  statusMessage,
  progress,
  confirming,
  confirmDeviceLabel,
  onSelectConfirmDevice,
  onScanForBoard,
  onFlash,
  onCancelConfirm,
  onConfirmFlash,
  onAbort,
}: WebFlashCardProps) {
  const t = useTranslations("flashTool.ados");

  const flashDisabled =
    isFlashing ||
    !allChecked ||
    !usbSupported ||
    !webFlashInstall.imageUrl ||
    devices.length === 0;

  return (
    <div className="bg-bg-secondary border border-border-default p-4 space-y-3">
      <h2 className="text-xs font-semibold text-text-primary flex items-center gap-2">
        <Usb size={14} />
        {t("webFlash.title")}
      </h2>

      {webFlashInstall.notes && webFlashInstall.notes.length > 0 && (
        <ul className="space-y-1 text-[10px] text-text-tertiary list-disc list-inside">
          {webFlashInstall.notes.map((note, i) => <li key={i}>{note}</li>)}
        </ul>
      )}

      {webFlashInstall.imageUrl ? (
        <div className="text-[10px] text-text-tertiary space-y-1">
          <p><span className="text-text-secondary">{t("webFlash.imageSizeLabel")}</span> {(webFlashInstall.imageSizeBytes / (1024 * 1024)).toFixed(1)} MB</p>
          <p className="font-mono break-all"><span className="text-text-secondary not-italic">{t("webFlash.sha256")}</span> {webFlashInstall.sha256}</p>
        </div>
      ) : (
        <p className="text-[10px] text-status-warning">
          {t("webFlash.noImage")}
        </p>
      )}

      <RockchipConnectionPanel
        devices={devices}
        usbSupported={usbSupported}
        isFlashing={isFlashing}
        onScan={onScanForBoard}
      />

      {statusMessage && !progress && (
        <p className="text-[10px] text-text-tertiary font-mono">{statusMessage}</p>
      )}

      {progress && (
        <div role="status" aria-live="polite" aria-atomic="true">
          <span className="sr-only">
            {t("a11y.flashStatus", {
              phase: progress.phase,
              percent: Math.floor(progress.percent),
            })}
          </span>
          <FirmwareFlashProgress
            progress={progress}
            isFlashing={isFlashing}
            onAbort={onAbort}
          />
        </div>
      )}

      {confirming && !isFlashing ? (
        <div className="border border-status-warning/40 bg-status-warning/5 p-3 space-y-2">
          <p className="text-[11px] text-status-warning font-semibold">
            {t("confirm.title")}
          </p>
          <p className="text-[10px] text-text-secondary">
            {t("confirm.body", { board: confirmDeviceLabel })}
          </p>
          {devices.length > 1 && (
            <Select
              value={confirmDeviceLabel}
              onChange={onSelectConfirmDevice}
              options={devices.map((d) => ({
                value: d.label,
                label: d.label,
              }))}
            />
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={onCancelConfirm}
              className="flex-1 px-3 py-1.5 text-[11px] font-semibold border border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-secondary cursor-pointer transition-colors"
            >
              {t("confirm.cancel")}
            </button>
            <button
              onClick={onConfirmFlash}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold border border-accent-primary bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 cursor-pointer transition-colors"
            >
              <Zap size={12} /> {t("confirm.confirm")}
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={onFlash}
          disabled={flashDisabled}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold border border-accent-primary bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          {isFlashing ? (
            <>
              <X size={12} /> {t("webFlash.flashing")}
            </>
          ) : (
            <>
              <Zap size={12} /> {t("webFlash.title")}
            </>
          )}
        </button>
      )}

      {!allChecked && webFlashInstall.imageUrl && (
        <p className="text-[10px] text-text-tertiary">
          {t("webFlash.checklistHint")}
        </p>
      )}
    </div>
  );
}
