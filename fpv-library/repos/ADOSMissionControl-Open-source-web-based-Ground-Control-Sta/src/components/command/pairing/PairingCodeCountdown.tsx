"use client";

/**
 * @module PairingCodeCountdown
 * @description MM:SS countdown reflecting the agent-authoritative
 * pairing-code expiry from the heartbeat (epoch seconds). Renders
 * nothing until the agent reports an expiry, so the component is
 * safe to mount unconditionally inside the pairing UI. Ticks every
 * five seconds; the rendered value is stale by at most that amount.
 * @license GPL-3.0-only
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";

const TICK_MS = 5_000;

function formatRemaining(seconds: number): string {
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export function PairingCodeCountdown() {
  const expiresAt = useAgentCapabilitiesStore((s) => s.pairingCodeExpiresAt);
  const t = useTranslations("pairing");
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    if (expiresAt == null) return;
    const id = setInterval(() => {
      setNow(Math.floor(Date.now() / 1000));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [expiresAt]);

  if (expiresAt == null) return null;

  const remaining = expiresAt - now;
  if (remaining <= 0) {
    return (
      <span className="text-xs font-medium text-status-warning">
        {t("codeExpired")}
      </span>
    );
  }

  return (
    <span className="text-xs text-text-tertiary">
      {t("codeExpiresIn", { time: formatRemaining(remaining) })}
    </span>
  );
}
