"use client";

/**
 * @module PairingCodeCard
 * @description Central pairing code state card. Shows sign-in CTA, error,
 * loading, expired, or active code with countdown plus install command.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Check,
  Copy,
  Loader2,
} from "lucide-react";

const INSTALL_URL =
  "https://raw.githubusercontent.com/altnautica/ADOSDroneAgent/main/scripts/install.sh";

export interface PairingCodeCardProps {
  codeError: string | null;
  code: string | null;
  expired: boolean;
  secondsLeft: number;
  copiedCode: boolean;
  copiedInstall: boolean;
  onRegenerate: () => void;
  onCopyCode: () => void;
  onCopyInstall: () => void;
}

export function getInstallCommand(c: string): string {
  return `curl -sSL ${INSTALL_URL} | sudo bash -s -- --pair ${c}`;
}

export function formatTime(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function PairingCodeCard({
  codeError,
  code,
  expired,
  secondsLeft,
  copiedCode,
  copiedInstall,
  onRegenerate,
  onCopyCode,
  onCopyInstall,
}: PairingCodeCardProps) {
  const tc = useTranslations("command");

  if (codeError) {
    return (
      <div className="p-5 bg-bg-secondary border border-status-error/30 rounded-lg text-center space-y-3">
        <div className="w-10 h-10 mx-auto rounded-full bg-status-error/15 flex items-center justify-center">
          <AlertTriangle size={18} className="text-status-error" />
        </div>
        <p className="text-sm font-medium text-text-primary">
          Could not generate a pairing code
        </p>
        <p className="text-xs text-status-error break-words">
          {codeError}
        </p>
        <button
          onClick={onRegenerate}
          className="px-4 py-1.5 text-xs font-medium bg-bg-tertiary border border-border-default rounded hover:bg-bg-primary transition-colors text-text-primary"
        >
          {tc("tryAgain")}
        </button>
      </div>
    );
  }

  if (!code) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <Loader2
          size={24}
          className="animate-spin text-accent-primary"
        />
        <p className="text-xs text-text-secondary">
          {tc("generatingCode")}
        </p>
      </div>
    );
  }

  if (expired) {
    return (
      <div className="flex flex-col items-center gap-4 py-6">
        <p className="text-sm text-text-secondary">
          {tc("codeExpiredShort")}
        </p>
        <button
          onClick={onRegenerate}
          className="px-4 py-1.5 text-xs font-medium bg-accent-primary text-white rounded hover:bg-accent-primary/90 transition-colors"
        >
          {tc("generateNewCode")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Big code display */}
      <div className="p-5 bg-bg-secondary border border-border-default rounded-lg text-center space-y-2">
        <div className="flex items-center justify-center gap-2">
          {code.split("").map((char, i) => (
            <span
              key={i}
              className="inline-flex items-center justify-center w-12 h-14 bg-bg-primary border border-border-default rounded text-2xl font-mono font-bold text-text-primary"
            >
              {char}
            </span>
          ))}
          <button
            onClick={onCopyCode}
            className="ml-2 p-2 text-text-tertiary hover:text-text-primary transition-colors"
            title={tc("copyCode")}
          >
            {copiedCode ? (
              <Check size={16} className="text-status-success" />
            ) : (
              <Copy size={16} />
            )}
          </button>
        </div>
        <p className="text-sm text-text-tertiary">
          {tc("expiresIn")}{" "}
          <span
            className={
              secondsLeft < 60
                ? "text-status-warning font-medium"
                : "font-medium text-text-secondary"
            }
          >
            {formatTime(secondsLeft)}
          </span>
        </p>
      </div>

      {/* Install command */}
      <div className="space-y-2">
        <p className="text-sm text-text-secondary">
          {tc("firstTimeColon")}
        </p>
        <div className="flex items-start gap-2 p-3 bg-bg-secondary border border-border-default rounded-lg">
          <code className="flex-1 text-xs font-mono text-text-secondary leading-relaxed break-all select-all">
            {getInstallCommand(code)}
          </code>
          <button
            onClick={onCopyInstall}
            className="p-1.5 text-text-tertiary hover:text-text-primary transition-colors shrink-0"
            title={tc("copyInstallCommand")}
          >
            {copiedInstall ? (
              <Check size={14} className="text-status-success" />
            ) : (
              <Copy size={14} />
            )}
          </button>
        </div>
        <p className="text-xs text-text-tertiary">
          {tc("alreadyInstalled")}{" "}
          <code className="font-mono text-text-secondary">
            sudo ados pair {code}
          </code>
        </p>
      </div>

      {/* Waiting indicator */}
      <div className="flex items-center justify-center gap-2 py-2">
        <Loader2
          size={14}
          className="animate-spin text-text-tertiary"
        />
        <p className="text-sm text-text-tertiary">
          {tc("waitingForDrone")}
        </p>
      </div>
    </div>
  );
}
