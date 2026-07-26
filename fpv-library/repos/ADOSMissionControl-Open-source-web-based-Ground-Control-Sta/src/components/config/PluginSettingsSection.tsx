/**
 * @module config/PluginSettingsSection
 * @description Renders the fleet `settings.section` slot inside the Settings
 * area. A GCS-level plugin that contributes a `settings.section` gets its
 * sandboxed iframe mounted here, under an "Extensions" heading on the general
 * Settings page. Inert until a plugin contributes — the `FleetPluginSlot`
 * renders nothing when the fleet producer yields no `settings.section`.
 *
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { Puzzle } from "lucide-react";

import { FleetPluginSlot } from "@/components/plugins/FleetPluginSlot";
import { useFleetPluginContributions } from "@/hooks/use-fleet-plugin-contributions";

export function PluginSettingsSection() {
  // Only render (and only call useTranslations) when a plugin actually
  // contributes a section, so the page stays clean on a GCS with no
  // settings-contributing plugin and a focused test needs no intl provider.
  const contributions = useFleetPluginContributions("settings.section");
  if (contributions.length === 0) return null;
  return <PluginSettingsSectionBody />;
}

function PluginSettingsSectionBody() {
  const t = useTranslations("plugins");
  return (
    <section className="space-y-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Puzzle size={14} className="text-accent-primary" />
        {t("settingsSectionHeading")}
      </h2>
      <FleetPluginSlot
        name="settings.section"
        className="space-y-3"
        iframeClassName="w-full h-64 border border-border-default rounded bg-bg-secondary"
      />
    </section>
  );
}
