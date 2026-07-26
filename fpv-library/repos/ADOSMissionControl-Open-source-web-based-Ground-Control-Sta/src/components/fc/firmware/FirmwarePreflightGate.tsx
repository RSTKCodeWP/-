"use client";

/**
 * Pre-flight environment gate for browser-based flashing. Web Serial / WebUSB
 * are Chromium-only and require a secure context (HTTPS or localhost). Shows a
 * compact "ready" strip when both hold, or a clear blocking card naming what is
 * missing — so a user on Firefox/Safari or an insecure origin never reaches a
 * dead "Flash" button.
 *
 * @module fc/firmware/FirmwarePreflightGate
 */

import { useEffect, useState } from "react";
import { Check, X, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

interface FirmwarePreflightGateProps {
  serialSupported: boolean;
  usbSupported: boolean;
}

export function FirmwarePreflightGate({ serialSupported, usbSupported }: FirmwarePreflightGateProps) {
  const t = useTranslations("flashTool.preflight");
  // Default optimistic so SSR/first paint doesn't flash a false warning.
  const [secure, setSecure] = useState(true);
  useEffect(() => {
    setSecure(typeof window === "undefined" ? true : window.isSecureContext);
  }, []);

  const apiOk = serialSupported || usbSupported;

  if (apiOk && secure) {
    return (
      <div className="flex items-center gap-2 text-[10px] text-status-success border border-status-success/30 bg-status-success/5 px-3 py-2">
        <Check size={12} />
        {t("ready")}
      </div>
    );
  }

  return (
    <div className="border border-status-error/40 bg-status-error/5 p-4 space-y-2">
      <p className="text-xs font-semibold text-status-error flex items-center gap-2">
        <ShieldAlert size={14} />
        {t("title")}
      </p>
      <GateRow ok={apiOk} label={t("chromium")} />
      <GateRow ok={secure} label={t("secureContext")} />
      {!apiOk && <p className="text-[10px] text-text-tertiary mt-1">{t("unsupported")}</p>}
      {!secure && <p className="text-[10px] text-text-tertiary mt-1">{t("insecure")}</p>}
    </div>
  );
}

function GateRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-[10px] text-text-secondary">
      {ok ? (
        <Check size={12} className="text-status-success" />
      ) : (
        <X size={12} className="text-status-error" />
      )}
      {label}
    </div>
  );
}
