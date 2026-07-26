"use client";

/**
 * @module FeatureGrid
 * @description Consumer-facing grid of agent capabilities shown on the
 * disconnected page.
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Code2,
  Cpu,
  Layers,
  Radio,
  Signal,
  Sparkles,
  Terminal,
  Video,
  Wifi,
} from "lucide-react";

const featureIcons = [
  Radio,
  Video,
  Signal,
  Wifi,
  Cpu,
  Sparkles,
  Layers,
  Terminal,
  Code2,
];

const featureKeys = [
  "mavlinkProxy",
  "hdVideo",
  "cellularTelemetry",
  "extendedRange",
  "plugAndPlay",
  "aiReady",
  "softwareDefined",
  "sshTerminal",
  "devTools",
] as const;

export function FeatureGrid() {
  const t = useTranslations("disconnectedPage");

  const features = useMemo(
    () =>
      featureKeys.map((key, i) => ({
        icon: featureIcons[i],
        title: t(key),
        description: t(`${key}Desc`),
      })),
    [t],
  );

  return (
    <div>
      <h2 className="text-lg font-medium text-text-primary mb-4">
        {t("turnAnyDrone")}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {features.map(({ icon: Icon, title, description }) => (
          <div
            key={title}
            className="p-5 bg-bg-secondary border border-border-default rounded space-y-2"
          >
            <div className="flex items-center gap-2">
              <Icon size={18} className="text-accent-primary" />
              <span className="text-sm font-medium text-text-primary">
                {title}
              </span>
            </div>
            <p className="text-xs text-text-tertiary leading-relaxed">
              {description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
