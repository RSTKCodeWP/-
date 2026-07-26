import { Activity, BellRing, BookOpen, Radio, Satellite } from "lucide-react";

import { useAlertStore } from "../store/alerts";
import { useSystemStore } from "../store/system";
import { statusTextClass } from "../ui/status";

/* The always-on system-health strip (impl-plan Task 5.3; DESIGN-SYSTEM §7.4). Degrade
 * visibly, never silently: link / telemetry / GPS / clock / heartbeat are ALWAYS present
 * (never-hidden trust fields, §6.8). Each reads the closed status set through one encoding.
 *
 * P0 rule: link-lost is a SYSTEM-INTEGRITY failure → critical (magenta), never warning
 * (orange — reserved for survivor world-urgency). */

interface StatusStripProps {
  /** UTC clock string, formatted by the caller (kept out so the component stays pure). */
  clock: string;
  /** Opens the in-app docs panel. Optional so the strip stays pure in component tests. */
  onOpenDocs?: () => void;
}

export function StatusStrip({ clock, onOpenDocs }: StatusStripProps) {
  const linkUp = useSystemStore((s) => s.linkUp);
  const telemetryAgeS = useSystemStore((s) => s.telemetryAgeS);
  const gpsFix = useSystemStore((s) => s.gpsFix);
  const gpsSats = useSystemStore((s) => s.gpsSats);
  const linkSeverity = useSystemStore((s) => s.linkSeverity());
  const telemetrySeverity = useSystemStore((s) => s.telemetrySeverity());
  const unackedCount = useAlertStore((s) => s.unackedSet.size);

  return (
    <div
      className="relative flex h-12 items-center gap-6 border-b border-hairline bg-surface-1 px-5 font-mono text-xs shadow-card"
      style={{ zIndex: "var(--z-status-strip)" }}
      data-testid="status-strip"
    >
      <span data-testid="strip-link" className={`flex items-center gap-2 ${statusTextClass(linkSeverity)}`}>
        <Radio size={14} aria-hidden />
        {linkUp ? "LINK OK" : "LINK LOST"}
      </span>

      <span
        data-testid="strip-telemetry"
        className={`flex items-center gap-2 ${statusTextClass(telemetrySeverity)}`}
      >
        <Activity size={14} aria-hidden />
        TEL {telemetryAgeS.toFixed(1)}s
      </span>

      <span data-testid="strip-gps" className="flex items-center gap-2 text-text-mid">
        <Satellite size={14} aria-hidden />
        GPS {gpsFix.toUpperCase()} · {gpsSats} sv
      </span>

      {unackedCount > 0 && (
        <span
          data-testid="strip-alerts"
          className="flex items-center gap-1 text-st-warning"
          title="unacknowledged high-priority contacts (burst-coalesced)"
        >
          <BellRing size={14} aria-hidden />
          {unackedCount} new
        </span>
      )}

      <span className="ml-auto text-text-mid">{clock}</span>

      {onOpenDocs && (
        <button
          type="button"
          data-testid="docs-toggle"
          onClick={onOpenDocs}
          aria-label="Open documentation"
          title="Documentation"
          className="flex items-center gap-1.5 text-text-mid hover:text-text-hi"
        >
          <BookOpen size={14} aria-hidden />
          DOCS
        </button>
      )}

      <Heartbeat />
    </div>
  );
}

/* The heartbeat pulses with real frame arrival (DESIGN-SYSTEM §4.6) — it is a positive
 * liveness cue, not a primary alarm (link-loss is signaled by the link slot flipping
 * critical above). The pulse animation is bound to data in 5.9; here it is the marker. */
function Heartbeat() {
  return (
    <span
      data-testid="strip-heartbeat"
      aria-label="liveness heartbeat"
      className="h-2 w-2 rounded-pill bg-st-nominal"
    />
  );
}
