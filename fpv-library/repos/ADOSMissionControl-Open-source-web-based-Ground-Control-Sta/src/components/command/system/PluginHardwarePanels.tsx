/**
 * @module command/system/PluginHardwarePanels
 * @description Renders the fleet `hardware.tab` slot inside the System tab's
 * Hardware area (and the ground-station Peripherals tab, which composes the
 * same component). A GCS-level plugin that contributes a `hardware.tab` gets
 * its sandboxed iframe mounted here under an "Extensions" heading. Inert until
 * a plugin contributes.
 *
 * The outer gate avoids calling `useTranslations` until a plugin actually
 * contributes, so a surface that hosts this with no plugin (and no intl
 * provider in a focused test) pays no hook cost and never throws.
 *
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { Puzzle } from "lucide-react";

import { FleetPluginSlot } from "@/components/plugins/FleetPluginSlot";
import { useFleetPluginContributions } from "@/hooks/use-fleet-plugin-contributions";

export function PluginHardwarePanels() {
  const contributions = useFleetPluginContributions("hardware.tab");
  if (contributions.length === 0) return null;
  return <PluginHardwarePanelsBody />;
}

function PluginHardwarePanelsBody() {
  const t = useTranslations("plugins");
  return (
    <section className="space-y-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Puzzle size={14} className="text-accent-primary" />
        {t("hardwarePanelsHeading")}
      </h2>
      <FleetPluginSlot
        name="hardware.tab"
        className="space-y-3"
        iframeClassName="w-full h-64 border border-border-default rounded bg-bg-secondary"
      />
    </section>
  );
}
