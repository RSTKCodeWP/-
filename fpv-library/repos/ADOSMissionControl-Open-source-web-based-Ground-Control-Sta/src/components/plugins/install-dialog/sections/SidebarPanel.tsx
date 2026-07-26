/**
 * @module SidebarPanel
 * @description Right rail of the plugin install review surface. Renders
 * a Details metadata block, a Compatibility status block, the single
 * Contents tree (permissions / FC params / telemetry / vendor binaries),
 * and a Links block — separated by 1px hairlines. Per UX research the
 * rail uses hairlines because it carries dense facts that need
 * scannable grouping; the main column intentionally has none.
 *
 * @license GPL-3.0-only
 */

"use client";

import { useState } from "react";
import { AlertTriangle, Check, ExternalLink, ImageOff } from "lucide-react";
import { useTranslations } from "next-intl";

import type { InstallManifestSummary } from "../types";
import type { CompatibilityResult } from "../check-compatibility";

import { SidebarContents } from "./SidebarContents";

const HAIRLINE = "border-t border-border-default/30";

export interface SidebarPanelProps {
  manifest: InstallManifestSummary;
  compatibility: CompatibilityResult;
  boardLabel: string;
  ramTotalMb?: number;
}

export function SidebarPanel({
  manifest,
  compatibility,
  boardLabel,
  ramTotalMb,
}: SidebarPanelProps) {
  const t = useTranslations("pluginInstall.review.sidebar");
  const tRoot = useTranslations("pluginInstall.review");

  return (
    <aside className="flex h-full flex-col overflow-y-auto px-4 py-4">
      <DetailsBlock manifest={manifest} t={t} />
      <div className={`${HAIRLINE} mt-4 pt-4`}>
        <CompatibilityBlock
          result={compatibility}
          boardLabel={boardLabel}
          ramTotalMb={ramTotalMb}
          manifest={manifest}
          t={t}
        />
      </div>
      <div className={`${HAIRLINE} mt-4 pt-4`}>
        <SectionLabel label={t("contents")} />
        <SidebarContents manifest={manifest} />
      </div>
      {manifest.screenshots && manifest.screenshots.length > 0 && (
        <div className={`${HAIRLINE} mt-4 pt-4`}>
          <ScreenshotsBlock
            screenshots={manifest.screenshots}
            label={t("screenshots")}
          />
        </div>
      )}
      <div className={`${HAIRLINE} mt-4 pt-4`}>
        <LinksBlock manifest={manifest} t={t} tRoot={tRoot} />
      </div>
    </aside>
  );
}

function ScreenshotsBlock({
  screenshots,
  label,
}: {
  screenshots: NonNullable<InstallManifestSummary["screenshots"]>;
  label: string;
}) {
  return (
    <div>
      <SectionLabel label={label} />
      <ul className="grid grid-cols-2 gap-2">
        {screenshots.map((shot, idx) => (
          <Screenshot key={`${shot.url}:${idx}`} shot={shot} />
        ))}
      </ul>
    </div>
  );
}

/** One gallery screenshot with a graceful fallback: a broken/unreachable image
 * URL renders a muted placeholder tile instead of the browser's broken glyph. */
function Screenshot({
  shot,
}: {
  shot: NonNullable<InstallManifestSummary["screenshots"]>[number];
}) {
  const [errored, setErrored] = useState(false);
  return (
    <li className="overflow-hidden rounded-md border border-border-default/40 bg-bg-tertiary/40">
      {errored ? (
        <div className="flex h-20 w-full items-center justify-center bg-bg-tertiary/40">
          <ImageOff className="h-5 w-5 text-text-tertiary/50" aria-hidden />
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={shot.url}
          alt={shot.caption ?? ""}
          className="h-20 w-full object-cover"
          loading="lazy"
          onError={() => setErrored(true)}
        />
      )}
      {shot.caption ? (
        <p className="truncate px-1.5 py-1 text-[10px] text-text-tertiary">
          {shot.caption}
        </p>
      ) : null}
    </li>
  );
}

type T = ReturnType<typeof useTranslations>;

function SectionLabel({ label }: { label: string }) {
  return (
    <h3 className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-text-tertiary">
      {label}
    </h3>
  );
}

function DetailsBlock({
  manifest,
  t,
}: {
  manifest: InstallManifestSummary;
  t: T;
}) {
  const [copied, setCopied] = useState(false);
  const sha = manifest.archiveSha256 ?? "";
  const signer = manifest.signerId;

  const copyHash = () => {
    if (!sha || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }
    void navigator.clipboard.writeText(sha).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div>
      <SectionLabel label={t("details")} />
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
        <Row label={t("version")} value={`v${manifest.version}`} />
        {manifest.license && (
          <Row label={t("license")} value={manifest.license} />
        )}
        {manifest.author && (
          <Row label={t("author")} value={manifest.author} />
        )}
        {signer && (
          <Row label={t("signer")} value={signer.slice(0, 16)} mono />
        )}
        {sha && (
          <>
            <dt className="text-text-tertiary">{t("sha256")}</dt>
            <dd className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={copyHash}
                aria-label={t("copyHash")}
                className="truncate font-mono text-[11px] text-text-primary hover:text-accent-primary"
              >
                {sha.slice(0, 16)}…
              </button>
              {copied && (
                <span className="text-[10px] text-status-success">
                  {t("copyHashCopied")}
                </span>
              )}
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}

function CompatibilityBlock({
  result,
  boardLabel,
  ramTotalMb,
  manifest,
  t,
}: {
  result: CompatibilityResult;
  boardLabel: string;
  ramTotalMb?: number;
  manifest: InstallManifestSummary;
  t: T;
}) {
  const ramRequired = manifest.resourceImpact?.ramMb;
  const cpuPeak = manifest.resourceImpact?.cpuPercentPeak;
  const ramText =
    ramRequired && ramTotalMb
      ? `${(ramRequired / 1024).toFixed(1)}/${(ramTotalMb / 1024).toFixed(1)} GB`
      : ramRequired
        ? `${ramRequired} MB`
        : "—";

  return (
    <div>
      <SectionLabel label={t("compatibility")} />
      <ul className="space-y-1.5 text-xs">
        <StatusRow
          ok={result.boardCompatible}
          okText={t("boardOk", { soc: boardLabel })}
          failText={t("boardFail", { soc: boardLabel })}
        />
        <StatusRow
          ok={result.ramOk}
          okText={t("ramOk", { ram: ramText })}
          failText={t("ramFail", { ram: ramText })}
        />
        {typeof cpuPeak === "number" && (
          <StatusRow
            ok={result.cpuOk}
            okText={t("cpuOk", { cpu: cpuPeak })}
            failText={t("cpuFail", { cpu: cpuPeak })}
          />
        )}
      </ul>
    </div>
  );
}

function LinksBlock({
  manifest,
  t,
  tRoot,
}: {
  manifest: InstallManifestSummary;
  t: T;
  tRoot: T;
}) {
  const links: Array<{ label: string; href: string }> = [];
  if (manifest.documentationUrl) {
    links.push({ label: t("documentation"), href: manifest.documentationUrl });
  }
  if (manifest.homepageUrl) {
    links.push({ label: t("repository"), href: manifest.homepageUrl });
  }
  if (links.length === 0) {
    return (
      <div>
        <SectionLabel label={t("links")} />
        <p className="text-xs text-text-tertiary">{tRoot("sourceLicense.docs")}: —</p>
      </div>
    );
  }
  return (
    <div>
      <SectionLabel label={t("links")} />
      <ul className="space-y-1.5 text-xs">
        {links.map((l) => (
          <li key={l.href}>
            <a
              href={l.href}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 text-text-primary hover:text-accent-primary"
            >
              {l.label}
              <ExternalLink size={11} className="text-text-tertiary" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <>
      <dt className="text-text-tertiary">{label}</dt>
      <dd
        className={
          "truncate text-text-primary " +
          (mono ? "font-mono text-[11px]" : "")
        }
      >
        {value}
      </dd>
    </>
  );
}

function StatusRow({
  ok,
  okText,
  failText,
}: {
  ok: boolean;
  okText: string;
  failText: string;
}) {
  return (
    <li className="flex items-start gap-2">
      {ok ? (
        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-success" />
      ) : (
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-warning" />
      )}
      <span className={ok ? "text-text-secondary" : "text-status-warning"}>
        {ok ? okText : failText}
      </span>
    </li>
  );
}
