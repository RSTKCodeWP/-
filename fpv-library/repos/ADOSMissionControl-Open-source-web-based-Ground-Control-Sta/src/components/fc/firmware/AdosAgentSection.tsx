"use client";

/**
 * @module AdosAgentSection
 * @description ADOS Agent flash flow section. Composes the target-board
 * picker with either the curl install card or the WebUSB flash card,
 * depending on the manifest entry the selected board carries.
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import type {
  AdosAgentBoard,
  AdosAgentStack,
  AdosAgentWebFlashInstall,
} from "@/lib/protocol/firmware/ados-agent-manifest";
import { RockchipBootromFlasher } from "@/lib/protocol/firmware/rockchip-bootrom";
import { usbDeviceManager, type UsbDeviceInfo } from "@/lib/usb-device-manager";
import { TargetBoardCard } from "./agent-stages/TargetBoardCard";
import { CurlInstallCard } from "./agent-stages/CurlInstallCard";
import { WebFlashCard } from "./agent-stages/WebFlashCard";
import { useRockchipFlash } from "./agent-stages/use-rockchip-flash";

interface Props {
  stack: AdosAgentStack;
  boards: AdosAgentBoard[];
  loading: boolean;
  error: string;
  agentVersion: string;
  selectedBoardId: string;
  setSelectedBoardId: (id: string) => void;
  onRetry: () => void;
  /**
   * Pre-flight checklist signal from the parent panel. Optional so
   * existing call sites (and tests) that rendered the section without
   * a checklist gate keep compiling; the live Flash Tool always passes
   * the real value.
   */
  allChecked?: boolean;
  /** WebUSB availability gate (already computed in parent). */
  usbSupported?: boolean;
  /**
   * Manifest origin marker. "github" means the upstream catalog
   * resolved cleanly; "fallback" means the proxy served the embedded
   * baseline. Drives the offline-catalog pill near the picker.
   */
  manifestSource?: string;
}

export function AdosAgentSection({
  stack, boards, loading, error, agentVersion,
  selectedBoardId, setSelectedBoardId, onRetry,
  allChecked = false, usbSupported = false,
  manifestSource,
}: Props) {
  const t = useTranslations("flashTool.ados");

  // Rockchip bootrom devices currently visible to the browser. Updated
  // on mount via getKnownDevices() and live via hot-plug listeners.
  const [rockchipDevices, setRockchipDevices] = useState<UsbDeviceInfo[]>([]);

  const eligibleBoards = useMemo(
    () => boards.filter((b) => b.stacks.includes(stack)),
    [boards, stack],
  );

  const selectedBoard = useMemo(
    () => eligibleBoards.find((b) => b.id === selectedBoardId) ?? null,
    [eligibleBoards, selectedBoardId],
  );

  const install = selectedBoard?.installs[stack] ?? null;
  const webFlashInstall =
    install && install.method === "web-flash"
      ? (install as AdosAgentWebFlashInstall)
      : null;

  // Subscribe to USB hot-plug for Rockchip devices. Mirrors the DFU
  // hook in useFirmwareState but scoped to the Rockchip vendor id. The
  // global manager is initialised by the parent FC flow on mount, so
  // we just attach connect/disconnect handlers here and filter for
  // Rockchip devices on each event.
  useEffect(() => {
    if (!usbSupported) return;
    let cancelled = false;
    usbDeviceManager.init();
    RockchipBootromFlasher.getKnownDevices()
      .then((devs) => {
        if (!cancelled) setRockchipDevices(devs);
      })
      .catch(() => {});
    const unsubConnect = usbDeviceManager.onConnect((info) => {
      if (info.isRockchip) {
        setRockchipDevices((prev) => [
          ...prev.filter((d) => d.label !== info.label),
          info,
        ]);
      }
    });
    const unsubDisconnect = usbDeviceManager.onDisconnect((info) => {
      if (info.isRockchip) {
        setRockchipDevices((prev) => prev.filter((d) => d.label !== info.label));
      }
    });
    return () => {
      cancelled = true;
      unsubConnect();
      unsubDisconnect();
    };
  }, [usbSupported]);

  const flash = useRockchipFlash({ webFlashInstall, rockchipDevices });

  const handleScanForBoard = useCallback(async () => {
    try {
      const device = await RockchipBootromFlasher.requestDevice();
      const info = usbDeviceManager.buildDeviceInfo(device);
      setRockchipDevices((prev) => [
        ...prev.filter((d) => d.label !== info.label),
        info,
      ]);
      flash.setStatusMessage(t("status.boardDetected", { label: info.label }));
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotFoundError") {
        flash.setStatusMessage(t("error.noBoardSelected"));
      } else {
        const msg = err instanceof Error ? err.message : t("error.unknown");
        if (!msg.includes("cancelled") && !msg.includes("aborted")) {
          flash.setStatusMessage(t("status.detectionFailed", { message: msg }));
        }
      }
    }
  }, [flash, t]);

  const stackLabel = stack === "ados-drone-agent" ? t("stack.drone") : t("stack.ground");

  return (
    <>
      <TargetBoardCard
        boards={eligibleBoards}
        selectedBoardId={selectedBoardId}
        onSelectBoardId={setSelectedBoardId}
        loading={loading}
        error={error}
        onRetry={onRetry}
        agentVersion={agentVersion}
        manifestSource={manifestSource}
        stackLabel={stackLabel}
      />

      {install && install.method === "curl" && (
        <CurlInstallCard
          install={install}
          resetSignal={`${selectedBoardId}|${stack}`}
        />
      )}

      {webFlashInstall && (
        <WebFlashCard
          webFlashInstall={webFlashInstall}
          devices={rockchipDevices}
          usbSupported={usbSupported}
          isFlashing={flash.isFlashing}
          allChecked={allChecked}
          statusMessage={flash.statusMessage}
          progress={flash.progress}
          confirming={flash.confirming}
          confirmDeviceLabel={flash.confirmDeviceLabel}
          onSelectConfirmDevice={flash.setConfirmDeviceLabel}
          onScanForBoard={handleScanForBoard}
          onFlash={flash.handleFlash}
          onCancelConfirm={flash.handleCancelConfirm}
          onConfirmFlash={flash.runFlash}
          onAbort={flash.handleAbort}
        />
      )}
    </>
  );
}
