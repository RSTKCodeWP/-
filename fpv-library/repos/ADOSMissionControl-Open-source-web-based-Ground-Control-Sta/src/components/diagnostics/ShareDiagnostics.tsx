"use client";

import { useCallback, useState } from "react";
import { useDiagnosticsStore } from "@/stores/diagnostics-store";
import { Share2, Check } from "lucide-react";

function buildCompactSnapshot(): Record<string, unknown> {
  const state = useDiagnosticsStore.getState();

  // Connection log with durations and error categories
  const connLog = state.connectionLog.map((c) => ({
    t: c.type,
    ts: c.timestamp,
    d: c.details,
    dur: c.durationMs,
    err: c.errorCategory,
  }));

  // Error counts by category
  const errorCounts: Record<string, number> = {};
  for (const entry of state.connectionLog) {
    if (entry.type === "error" && entry.errorCategory) {
      errorCounts[entry.errorCategory] = (errorCounts[entry.errorCategory] ?? 0) + 1;
    }
  }

  // Recent events (last 20)
  const events = state.eventTimeline.toArray().slice(-20).map((e) => ({
    t: e.type,
    ts: e.timestamp,
    d: e.description,
  }));

  // Message rate summary
  const rates = Array.from(state.messageRates.values())
    .filter((r) => r.hz > 0)
    .map((r) => ({ n: r.msgName, hz: Math.round(r.hz * 10) / 10 }));

  return {
    v: 1,
    at: Date.now(),
    conn: connLog,
    errs: errorCounts,
    evts: events,
    rates,
    perf: state.performanceMetrics,
  };
}

export function ShareDiagnostics() {
  const [copied, setCopied] = useState(false);

  const handleShare = useCallback(async () => {
    const snapshot = buildCompactSnapshot();
    const json = JSON.stringify(snapshot);
    const encoded = btoa(json);
    const url = `${window.location.origin}${window.location.pathname}?diag=${encoded}`;

    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement("textarea");
      textarea.value = url;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, []);

  return (
    <button
      onClick={handleShare}
      className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] text-text-secondary hover:text-text-primary cursor-pointer border border-border-default hover:border-text-tertiary transition-colors"
    >
      {copied ? <Check size={10} className="text-status-success" /> : <Share2 size={10} />}
      {copied ? "URL Copied" : "Share Diagnostics"}
    </button>
  );
}
