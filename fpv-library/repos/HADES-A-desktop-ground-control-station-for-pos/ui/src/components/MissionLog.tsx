import { useMissionLog, type LogKind } from "../store/missionLog";
import { formatUtcClock } from "../ui/format";

/* The append-only mission log foot drawer (impl-plan Task 5.8). A timestamped audit trail of
 * every detection / clearance change / dispatch snapshot / note / link event. Newest at the
 * bottom (chronological). Compact mono rows; a kind glyph for quick scanning. */

const KIND_GLYPH: Record<LogKind, string> = {
  detection: "◉",
  clearance: "▸",
  snapshot: "⌖",
  note: "✎",
  link: "⚡",
};

const KIND_CLASS: Record<LogKind, string> = {
  detection: "text-st-warning",
  clearance: "text-blue-bright",
  snapshot: "text-st-info",
  note: "text-text-mid",
  link: "text-st-critical",
};

export function MissionLog() {
  const entries = useMissionLog((s) => s.entries);

  if (entries.length === 0) {
    return (
      <div className="px-4 py-2 font-mono text-2xs text-text-lo">
        Mission log — no events yet
      </div>
    );
  }

  // show the most recent entries in the foot drawer; full history scrolls
  const recent = entries.slice(-200);
  return (
    <div className="max-h-[160px] overflow-auto px-3 py-1 font-mono text-2xs" aria-label="Mission log">
      {recent.map((e) => (
        <div key={e.id} className="flex items-baseline gap-2 py-px">
          <span className="text-text-lo">{formatUtcClock(new Date(e.t))}</span>
          <span className={KIND_CLASS[e.kind]} aria-hidden>
            {KIND_GLYPH[e.kind]}
          </span>
          <span className="text-text-mid">{e.text}</span>
        </div>
      ))}
    </div>
  );
}
