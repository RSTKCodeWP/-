"use client";

/**
 * @module fc/firmware/agent-stages/RockchipConnectionPanel
 * @description Status panel for the Rockchip flash flow. Shows the
 * "no board connected" prompt with a Scan button, or the green
 * "ready to flash" banner once at least one Rockchip device is
 * visible to the browser.
 * @license GPL-3.0-only
 */

import { Usb } from "lucide-react";
import { useTranslations } from "next-intl";
import { ROCKCHIP_USB_VID } from "@/lib/protocol/firmware/rockchip-bootrom";
import type { UsbDeviceInfo } from "@/lib/usb-device-manager";
import { hex } from "./utils";

export interface RockchipConnectionPanelProps {
  devices: UsbDeviceInfo[];
  usbSupported: boolean;
  isFlashing: boolean;
  onScan: () => void;
}

export function RockchipConnectionPanel({
  devices,
  usbSupported,
  isFlashing,
  onScan,
}: RockchipConnectionPanelProps) {
  const t = useTranslations("flashTool.ados");
  if (devices.length > 0) {
    return (
      <div
        className="border border-status-success/40 bg-status-success/5 p-3 space-y-1"
        aria-live="polite"
        aria-label={t("a11y.connectionStatusRegion")}
      >
        <p className="text-[11px] text-status-success font-semibold">{t("connection.boardConnected")}</p>
        <p className="text-[10px] text-text-secondary">
          {t("connection.readyToFlash", { devices: devices.map((d) => d.label).join(", ") })}
        </p>
      </div>
    );
  }
  return (
    <div
      className="border border-border-default bg-bg-tertiary p-3 space-y-2"
      aria-live="polite"
      aria-label={t("a11y.connectionStatusRegion")}
    >
      <p className="text-[11px] text-text-secondary font-semibold">{t("connection.noBoardConnected")}</p>
      <p className="text-[10px] text-text-tertiary">
        {t("connection.scanHint", { vendor: hex(ROCKCHIP_USB_VID) })}
      </p>
      {usbSupported && (
        <button
          onClick={onScan}
          disabled={isFlashing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold border border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-secondary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          <Usb size={12} /> {t("connection.scanForBoard")}
        </button>
      )}
    </div>
  );
}
