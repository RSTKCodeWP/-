/**
 * @module SidebarContents
 * @description Flat-list contents block for the right sidebar. Replaces
 * the earlier tree presentation: every category subheader is static
 * text (no toggle, no chevron) and every item underneath renders inline
 * so the operator sees the whole plugin manifest at a glance. Visual
 * style mirrors the CompatibilityBlock above — Lucide icon prefix on
 * each category header, leading middle-dot on each item row.
 *
 * @license GPL-3.0-only
 */

"use client";

import type { ReactNode } from "react";
import { ExternalLink, Package, Radio, Sliders } from "lucide-react";
import { useTranslations } from "next-intl";

import type { InstallManifestSummary } from "../types";

export function SidebarContents({
  manifest,
}: {
  manifest: InstallManifestSummary;
}) {
  const tTree = useTranslations("pluginInstall.review.tree");

  const fcParams = collectFcParameters(manifest.requiredFcParameters);
  const telemetry = manifest.telemetryFields ?? [];
  const vendor = manifest.vendorAttribution ?? [];

  if (fcParams.length === 0 && telemetry.length === 0 && vendor.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {fcParams.length > 0 && (
        <ContentsGroup
          icon={<Sliders className="h-3.5 w-3.5 text-text-tertiary" />}
          heading={tTree("fcParameters", { count: fcParams.length })}
        >
          {fcParams.map((row, i) => (
            <ItemRow
              key={`${row.firmware}:${row.param}:${i}`}
              primary={row.param}
              mono
              trailing={
                <span className="text-text-tertiary">({row.firmware})</span>
              }
            />
          ))}
        </ContentsGroup>
      )}

      {telemetry.length > 0 && (
        <ContentsGroup
          icon={<Radio className="h-3.5 w-3.5 text-text-tertiary" />}
          heading={tTree("telemetryTopics", { count: telemetry.length })}
        >
          {telemetry.map((topic, i) => (
            <ItemRow key={`${topic}:${i}`} primary={topic} mono />
          ))}
        </ContentsGroup>
      )}

      {vendor.length > 0 && (
        <ContentsGroup
          icon={<Package className="h-3.5 w-3.5 text-text-tertiary" />}
          heading={tTree("vendorBinaries", { count: vendor.length })}
        >
          {vendor.map((v, i) => (
            <ItemRow
              key={`${v.name ?? "vendor"}:${i}`}
              primary={v.name ?? "—"}
              trailing={
                <span className="inline-flex items-center gap-1 text-text-tertiary">
                  {v.license && (
                    <span className="text-[10px]">{v.license}</span>
                  )}
                  {v.source_url && (
                    <a
                      href={v.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center hover:text-accent-primary"
                      aria-label={`${v.name ?? "vendor"} source`}
                    >
                      <ExternalLink size={11} />
                    </a>
                  )}
                </span>
              }
            />
          ))}
        </ContentsGroup>
      )}
    </div>
  );
}

function ContentsGroup({
  icon,
  heading,
  children,
}: {
  icon: ReactNode;
  heading: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-text-secondary">
        {icon}
        <span>{heading}</span>
      </div>
      <ul className="space-y-1">{children}</ul>
    </div>
  );
}

function ItemRow({
  primary,
  trailing,
  mono,
}: {
  primary: string;
  trailing?: ReactNode;
  mono?: boolean;
}) {
  return (
    <li className="flex items-start gap-1.5 text-xs">
      <span className="select-none text-text-tertiary">·</span>
      <span
        className={
          "min-w-0 flex-1 truncate text-text-secondary " +
          (mono ? "font-mono text-[11px]" : "")
        }
      >
        {primary}
      </span>
      {trailing && <span className="shrink-0 text-xs">{trailing}</span>}
    </li>
  );
}

type FcRow = { firmware: "ArduPilot" | "PX4" | "iNav"; param: string };

function collectFcParameters(
  rfp: InstallManifestSummary["requiredFcParameters"],
): FcRow[] {
  const out: FcRow[] = [];
  if (!rfp) return out;
  for (const p of rfp.ardupilot ?? []) out.push({ firmware: "ArduPilot", param: p.param });
  for (const p of rfp.px4 ?? []) out.push({ firmware: "PX4", param: p.param });
  for (const p of rfp.inav ?? []) out.push({ firmware: "iNav", param: p.param });
  return out;
}
