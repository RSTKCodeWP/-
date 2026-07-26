"use client";

/**
 * @module fc/firmware/agent-stages/CurlInstallCard
 * @description Renders the curl one-liner install card for boards
 * whose ADOS Agent install method is `curl`. Includes a copy button
 * with a transient confirmation pip and a setup-hint pointing the
 * operator at the captive portal.
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Info, Terminal } from "lucide-react";
import { useTranslations } from "next-intl";

export interface CurlInstall {
  command: string;
  notes?: string[];
}

export interface CurlInstallCardProps {
  install: CurlInstall;
  /**
   * Bumped by the parent when the operator switches board or stack so
   * the green copy-confirm pip from the prior selection doesn't leak
   * onto a new command.
   */
  resetSignal: string;
}

export function CurlInstallCard({ install, resetSignal }: CurlInstallCardProps) {
  const t = useTranslations("flashTool.ados");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setCopied(false);
  }, [resetSignal]);

  const copyCommand = useCallback(async (cmd: string) => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write can fail in non-secure contexts. The textarea
      // below stays selectable as a manual fallback.
    }
  }, []);

  return (
    <div className="bg-bg-secondary border border-border-default p-4 space-y-3">
      <h2 className="text-xs font-semibold text-text-primary flex items-center gap-2">
        <Terminal size={14} />
        {t("curl.title")}
      </h2>

      {install.notes && install.notes.length > 0 && (
        <ul className="space-y-1 text-[10px] text-text-tertiary list-disc list-inside">
          {install.notes.map((note, i) => <li key={i}>{note}</li>)}
        </ul>
      )}

      <div className="relative">
        <pre className="bg-bg-tertiary border border-border-default p-3 pr-12 text-[11px] text-text-secondary font-mono overflow-x-auto whitespace-pre break-words">
          {install.command}
        </pre>
        <button
          onClick={() => copyCommand(install.command)}
          aria-pressed={copied}
          aria-label={copied ? t("a11y.copyButtonCopied") : t("a11y.copyButtonCopy")}
          className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 text-[10px] font-semibold border border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-secondary cursor-pointer transition-colors">
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? t("common.copied") : t("common.copy")}
        </button>
        <span className="sr-only" aria-live="polite">
          {copied ? t("a11y.copyAnnounce") : ""}
        </span>
      </div>

      <div className="flex items-start gap-2 text-[10px] text-text-tertiary">
        <Info size={11} className="mt-0.5 flex-shrink-0" />
        <p>
          {t("curl.setupHintBefore")}<code className="text-text-secondary">http://&lt;board-ip&gt;:8080</code>{t("curl.setupHintAfter")}
        </p>
      </div>
    </div>
  );
}
