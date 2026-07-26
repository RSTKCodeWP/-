/**
 * @module ReviewStage
 * @description Two-column install review surface. Composes the sticky header
 * (identity + badge row), a sticky sub-bar (install destinations + a jump-to
 * permissions pill), the scrolling main column (about / features /
 * contributions / hardware access / permissions / requirements), the right
 * rail (details + compatibility + contents + links + screenshots), and the
 * sticky footer with the CTA pair.
 *
 * The information architecture follows a VS-Code "feature contributions" model
 * with progressive disclosure: what the plugin adds to Mission Control reads
 * first, the permission grant is one click away via the sub-bar pill, and the
 * denser requirement facts sit at the bottom.
 *
 * @license GPL-3.0-only
 */

"use client";

import type { ReactNode } from "react";
import { ShieldQuestion } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { CapabilityChips } from "@/components/plugins/CapabilityChips";
import { PluginContributions } from "@/components/plugins/contributions/PluginContributions";

import type { InstallManifestSummary } from "../types";
import type { CompatibilityResult } from "../check-compatibility";

import { PermissionsSection } from "./PermissionsSection";
import { ReviewHeader } from "./ReviewHeader";
import { SidebarPanel } from "./SidebarPanel";

const PERMISSIONS_ANCHOR = "plugin-install-permissions";

export interface ReviewStageProps {
  manifest: InstallManifestSummary;
  iconUrl?: string;
  targetName: string;
  /** Drone the agent half installs on, or null when the plugin has no
   * agent half / is being installed from the no-drone Settings home.
   * Drives the two-destination breakdown. */
  agentTargetName?: string | null;
  boardLabel: string;
  ramTotalMb?: number;
  compatibility: CompatibilityResult;
  granted: Set<string>;
  onTogglePermission: (id: string, required: boolean) => void;
  onCancel: () => void;
  onInstall: () => void;
}

export function ReviewStage({
  manifest,
  iconUrl,
  targetName,
  agentTargetName,
  boardLabel,
  ramTotalMb,
  compatibility,
  granted,
  onTogglePermission,
  onCancel,
  onInstall,
}: ReviewStageProps) {
  const t = useTranslations("pluginInstall.review");

  const installDisabled = !compatibility.boardCompatible;
  // The footer counts what the operator is actually approving (the granted
  // set). The sub-bar pill counts the full permission surface to review. They
  // are labelled distinctly, and a plugin that grants nothing reads "Install"
  // rather than the confusing "grants 0" next to an "N permissions" pill.
  const grantedCount = granted.size;
  const permissionsTotal = manifest.permissions.length;

  const scrollToPermissions = () => {
    if (typeof document === "undefined") return;
    document
      .getElementById(PERMISSIONS_ANCHOR)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[1fr_360px] min-h-0 overflow-hidden">
      <div className="flex min-h-0 flex-col overflow-hidden border-r border-border-default/30">
        <ReviewHeader
          manifest={manifest}
          iconUrl={iconUrl}
          targetName={targetName}
          boardLabel={boardLabel}
          compatible={compatibility.boardCompatible}
          onClose={onCancel}
        />
        <SubBar
          halves={manifest.halves}
          agentTargetName={agentTargetName ?? null}
          permissionsTotal={permissionsTotal}
          onJumpToPermissions={scrollToPermissions}
        />
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="space-y-8">
            {manifest.descriptionLong || manifest.description ? (
              <AboutSection
                shortText={manifest.description}
                longText={manifest.descriptionLong}
                title={t("about.title")}
              />
            ) : null}

            {manifest.features && manifest.features.length > 0 && (
              <FeaturesSection
                title={t("features.title")}
                features={manifest.features}
              />
            )}

            <PluginContributions manifest={manifest} />

            <CapabilityChips
              permissions={manifest.permissions}
              vendorAttribution={manifest.vendorAttribution}
              title={t("hardwareAccess.title")}
            />

            <section id={PERMISSIONS_ANCHOR} className="scroll-mt-4">
              <PermissionsSection
                manifest={manifest}
                granted={granted}
                onToggle={onTogglePermission}
              />
            </section>

            <RequirementsSection manifest={manifest} />
          </div>
        </div>
        <footer className="sticky bottom-0 z-10 flex items-center justify-end gap-3 border-t border-border-default/30 bg-bg-secondary px-6 py-4">
          <Button variant="ghost" onClick={onCancel}>
            {t("cancel")}
          </Button>
          <Button
            onClick={onInstall}
            disabled={installDisabled}
            title={
              installDisabled ? t("installDisabledNotCompatible") : undefined
            }
          >
            {grantedCount > 0
              ? t("installGrants", { n: grantedCount })
              : t("install")}
          </Button>
        </footer>
      </div>
      <SidebarPanel
        manifest={manifest}
        compatibility={compatibility}
        boardLabel={boardLabel}
        ramTotalMb={ramTotalMb}
      />
    </div>
  );
}

/**
 * Sticky sub-bar below the header: the two-destination breakdown on the left
 * and a "N permissions" pill on the right that jumps to the permissions
 * section so consent is one click away while the operator reads.
 */
function SubBar({
  halves,
  agentTargetName,
  permissionsTotal,
  onJumpToPermissions,
}: {
  halves: ReadonlyArray<"agent" | "gcs">;
  agentTargetName: string | null;
  permissionsTotal: number;
  onJumpToPermissions: () => void;
}) {
  const t = useTranslations("pluginInstall.review");
  const hasAgent = halves.includes("agent");
  const hasGcs = halves.includes("gcs");
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 border-b border-border-default/30 bg-bg-tertiary/30 px-6 py-2.5 text-xs">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        {hasAgent && (
          <span className="flex items-center gap-1.5">
            <span className="font-medium text-text-secondary">
              {t("destinations.agentHalf")}
            </span>
            <span className="text-text-tertiary" aria-hidden>
              →
            </span>
            {agentTargetName ? (
              <span className="text-text-primary">{agentTargetName}</span>
            ) : (
              <span className="text-status-warning">
                {t("destinations.perDrone")}
              </span>
            )}
          </span>
        )}
        {hasGcs && (
          <span className="flex items-center gap-1.5">
            <span className="font-medium text-text-secondary">
              {t("destinations.gcsHalf")}
            </span>
            <span className="text-text-tertiary" aria-hidden>
              →
            </span>
            <span className="text-text-primary">
              {t("destinations.thisMissionControl")}
            </span>
          </span>
        )}
      </div>
      {permissionsTotal > 0 && (
        <button
          type="button"
          onClick={onJumpToPermissions}
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default/50 bg-bg-secondary px-2.5 py-1 font-medium text-text-secondary transition-colors hover:border-accent-primary/50 hover:text-text-primary"
        >
          <ShieldQuestion className="h-3.5 w-3.5" aria-hidden />
          {t("permissionsAnchor", { count: permissionsTotal })}
        </button>
      )}
    </div>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <h3 className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-text-tertiary">
      {label}
    </h3>
  );
}

/** Render a paragraph chunk that may start with a `**Heading**` line.
 * If the first line is wrapped in `**...**`, lift it into a bold heading
 * stacked above the body. Inline `**...**` spans elsewhere in the body
 * render as <strong>. Anything else passes through as plain text with
 * `whitespace-pre-line` so single newlines in the source survive. */
function renderRichBold(text: string): ReactNode {
  const newlineIdx = text.indexOf("\n");
  const firstLine = newlineIdx === -1 ? text : text.slice(0, newlineIdx);
  const rest = newlineIdx === -1 ? "" : text.slice(newlineIdx + 1).trim();
  const headingMatch = firstLine.match(/^\*\*(.+?)\*\*[.:]?\s*$/);
  if (headingMatch) {
    return (
      <>
        <p className="mb-1 text-sm font-semibold text-text-primary">
          {headingMatch[1].replace(/\*\*(.+?)\*\*/g, "$1")}
        </p>
        {rest && (
          <p className="whitespace-pre-line text-sm leading-relaxed text-text-secondary">
            {renderInlineBold(rest)}
          </p>
        )}
      </>
    );
  }
  return (
    <p className="whitespace-pre-line text-sm leading-relaxed text-text-secondary">
      {renderInlineBold(text)}
    </p>
  );
}

/** Replace `**span**` runs with <strong>span</strong>. */
function renderInlineBold(text: string): ReactNode {
  const parts: ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }
    parts.push(<strong key={match.index}>{match[1]}</strong>);
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts.length > 0 ? parts : text;
}

function AboutSection({
  title,
  shortText,
  longText,
}: {
  title: string;
  shortText?: string;
  longText?: string;
}) {
  const paragraphs = longText
    ? longText
        .split(/\n\s*\n/)
        .map((chunk) => chunk.trim())
        .filter((chunk) => chunk.length > 0)
    : [];
  return (
    <section>
      <SectionLabel label={title} />
      <div className="space-y-4">
        {shortText && (
          <p className="text-sm leading-relaxed text-text-primary">
            {shortText}
          </p>
        )}
        {paragraphs.map((para, idx) => (
          <div key={idx} className="space-y-0">
            {renderRichBold(para)}
          </div>
        ))}
      </div>
    </section>
  );
}

function FeaturesSection({
  title,
  features,
}: {
  title: string;
  features: ReadonlyArray<string>;
}) {
  return (
    <section>
      <SectionLabel label={title} />
      <ul className="space-y-1.5 text-sm text-text-secondary">
        {features.map((f, idx) => (
          <li key={idx} className="flex items-start gap-2">
            <span className="mt-1 text-text-tertiary" aria-hidden>
              ·
            </span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The requirements block: forecast resource impact, hardware requirements,
 * and per-firmware FC parameter hints. Renders nothing when the plugin
 * declares none of them. */
function RequirementsSection({
  manifest,
}: {
  manifest: InstallManifestSummary;
}) {
  const t = useTranslations("pluginInstall.review");
  const impact = manifest.resourceImpact;
  const hasHardware = hasHardwareRequirements(manifest);
  const hasParams = hasFcParameters(manifest);
  if (!impact && !hasHardware && !hasParams) return null;
  return (
    <section>
      <SectionLabel label={t("requirements.title")} />
      <div className="space-y-4">
        {impact && <ResourceImpactSection impact={impact} />}
        {hasHardware && <HardwareRequirements manifest={manifest} />}
        {hasParams && <FcParametersTable manifest={manifest} />}
      </div>
    </section>
  );
}

function ResourceImpactSection({
  impact,
}: {
  impact: NonNullable<InstallManifestSummary["resourceImpact"]>;
}) {
  const t = useTranslations("pluginInstall.review.resourceGrid");
  const cells: Array<{ label: string; value: string }> = [];
  if (typeof impact.outputRateHz === "number") {
    cells.push({
      label: t("output"),
      value: `${impact.outputRateHz} ${t("units.hz")}`,
    });
  } else if (typeof impact.cpuPercentPeak === "number") {
    cells.push({
      label: t("cpu"),
      value: `${impact.cpuPercentPeak}${t("units.percent")}`,
    });
  }
  if (typeof impact.ramMb === "number") {
    cells.push({ label: t("ram"), value: `${impact.ramMb} ${t("units.mb")}` });
  }
  if (typeof impact.pids === "number") {
    cells.push({ label: t("pids"), value: String(impact.pids) });
  }
  if (typeof impact.startupTimeSeconds === "number") {
    cells.push({
      label: t("startup"),
      value: `${impact.startupTimeSeconds} ${t("units.seconds")}`,
    });
  }
  if (cells.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-3 rounded-xl bg-bg-tertiary/40 px-5 py-4 sm:grid-cols-4">
      {cells.map((c) => (
        <div key={c.label} className="flex flex-col items-start">
          <span className="text-2xl font-semibold tabular-nums text-text-primary">
            {c.value}
          </span>
          <span className="mt-0.5 text-[11px] uppercase tracking-wide text-text-tertiary">
            {c.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function hasHardwareRequirements(manifest: InstallManifestSummary): boolean {
  const h = manifest.hardwareRequirements;
  if (!h) return false;
  return !!(
    h.cameras ||
    h.fcFirmware ||
    (h.boards && h.boards.length) ||
    (h.optional && h.optional.length)
  );
}

function HardwareRequirements({
  manifest,
}: {
  manifest: InstallManifestSummary;
}) {
  const t = useTranslations("pluginInstall.review.hardwareReq");
  const h = manifest.hardwareRequirements;
  if (!h) return null;
  const rows: Array<{ label: string; value: string }> = [];
  if (h.cameras) rows.push({ label: t("cameras"), value: h.cameras });
  if (h.fcFirmware) rows.push({ label: t("fcFirmware"), value: h.fcFirmware });
  if (h.boards && h.boards.length > 0) {
    rows.push({ label: t("boards"), value: h.boards.join(", ") });
  }
  if (h.optional && h.optional.length > 0) {
    rows.push({ label: t("optional"), value: h.optional.join(", ") });
  }
  if (rows.length === 0) return null;
  return (
    <div className="space-y-2 rounded-xl bg-bg-tertiary/40 px-5 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiary">
        {t("title")}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
        {rows.map((r) => (
          <div key={r.label} className="contents">
            <dt className="text-text-tertiary">{r.label}</dt>
            <dd className="text-text-secondary">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function hasFcParameters(manifest: InstallManifestSummary): boolean {
  const g = manifest.requiredFcParameters;
  if (!g) return false;
  return !!(
    (g.ardupilot && g.ardupilot.length) ||
    (g.px4 && g.px4.length) ||
    (g.inav && g.inav.length)
  );
}

function FcParametersTable({ manifest }: { manifest: InstallManifestSummary }) {
  const t = useTranslations("pluginInstall.review.fcParamsTable");
  const groups = manifest.requiredFcParameters;
  if (!groups) return null;
  return (
    <div className="space-y-3 rounded-xl bg-bg-tertiary/40 px-5 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-tertiary">
        {t("title")}
      </p>
      {(["ardupilot", "px4", "inav"] as const).map((firmware) => {
        const rows = groups[firmware];
        if (!rows || rows.length === 0) return null;
        return (
          <div key={firmware}>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
              {firmware}
            </p>
            <ul className="space-y-0.5 text-text-secondary">
              {rows.map((row, idx) => (
                <li
                  key={`${firmware}.${idx}`}
                  className="grid grid-cols-[1fr_auto_2fr] items-baseline gap-3 font-mono text-[11px]"
                >
                  <span className="truncate text-text-primary">
                    {row.param}
                  </span>
                  <span className="text-text-tertiary">
                    {row.value !== undefined ? `= ${row.value}` : ""}
                  </span>
                  <span className="truncate text-text-tertiary">
                    {row.note ?? ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
