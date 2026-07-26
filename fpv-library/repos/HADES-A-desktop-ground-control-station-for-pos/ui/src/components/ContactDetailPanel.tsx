import { ArrowUpFromDot, Crosshair, RotateCcw, Send } from "lucide-react";

import { useClearanceStore } from "../store/clearanceStore";
import { useContactStore } from "../store/contacts";
import { nextClearance, prevClearance, primaryVerb } from "../store/dispatch";
import { useMissionLog } from "../store/missionLog";
import { useSelectionStore } from "../store/selection";
import { useSystemStore } from "../store/system";
import { commandSink } from "../ws/commandSink";
import { formatContactCoord } from "../ui/coords";
import { effectiveLocConf, isContactStale } from "../ui/degrade";
import { formatAge } from "../ui/format";
import { ConfidenceBar } from "./ConfidenceBar";
import { Placeholder } from "./Placeholder";

/* The canonical Contact detail / command panel (impl-plan Task 5.7a/c; DESIGN-SYSTEM §7.3).
 * One primary verb per clearance state, reversible (life-safety undo). Coordinate readout in
 * BOTH roles (MGRS primary + WGS84 DDM secondary), datum-explicit, radio-speakable. Every
 * trust field is shown, never hidden (§6.8): both confidences separately, age, R95, the
 * convergence + heading-limited flags. Localization confidence collapses live as telemetry
 * goes stale (M12 degrade-visibly). */

const FRAME_RATE = 30;
// for v1, the wire doesn't carry per-contact datum; the validation path is REL_TAKEOFF (.srt).
const DATUM = "REL_TAKEOFF";

export function ContactDetailPanel() {
  const selectedId = useSelectionStore((s) => s.selectedId);
  const contact = useContactStore((s) => (selectedId !== null ? s.contacts.get(selectedId) : undefined));
  const clearance = useClearanceStore((s) => (selectedId !== null ? s.states.get(selectedId) : undefined)) ?? "NEW";
  const setClearance = useClearanceStore((s) => s.set);
  const snapshot = useClearanceStore((s) => s.snapshot);
  const telemetryAgeS = useSystemStore((s) => s.telemetryAgeS);

  if (selectedId === null || !contact) {
    return <Placeholder label="Select a contact" hint="Click a pin, row, or video box" />;
  }

  const coord = formatContactCoord(contact.lat, contact.lon, DATUM);
  const effLoc = effectiveLocConf(contact.localization_conf, telemetryAgeS);
  const stale = isContactStale(telemetryAgeS);

  const logEvent = (kind: "clearance" | "snapshot", text: string) =>
    useMissionLog.getState().append({ kind, text, t: Date.now() });

  const advance = () => {
    const next = nextClearance(clearance);
    if (clearance === "NEW" && next === "ASSIGNED" && contact.lat !== null && contact.lon !== null) {
      snapshot(contact.track_id, contact.lat, contact.lon); // capture dispatch coordinate
      logEvent("snapshot", `trk ${contact.track_id} dispatch coord captured`);
    }
    setClearance(contact.track_id, next);
    logEvent("clearance", `trk ${contact.track_id} → ${next.replace("_", " ")}`);
  };
  const undo = () => {
    const prev = prevClearance(clearance);
    setClearance(contact.track_id, prev);
    logEvent("clearance", `trk ${contact.track_id} ↺ ${prev.replace("_", " ")}`);
  };

  return (
    <div data-testid="contact-detail" className="flex flex-col gap-4 p-5 font-mono text-xs">
      <div className="flex items-baseline justify-between">
        <span className="font-ui text-2xs font-semibold uppercase tracking-[0.08em] text-text-lo">
          Contact{" "}
          <span data-testid="detail-track" className="font-mono text-xl font-medium tracking-tight text-text-hi">
            {contact.track_id}
          </span>
        </span>
        <span className="font-ui text-2xs font-semibold uppercase tracking-wide text-text-lo">
          {contact.actionability_class}
        </span>
      </div>

      {/* two confidence axes, never merged; bar + EXACT value (§7.3); LOC is telemetry-collapsed */}
      <div className="flex gap-6">
        <span className="flex items-center gap-2 text-text-lo">
          DET <ConfidenceBar value={contact.detection_conf} label="detection confidence" showValue />
        </span>
        <span className="flex items-center gap-2 text-text-lo">
          LOC{" "}
          <ConfidenceBar
            value={contact.lat === null ? null : effLoc}
            label="localization confidence"
            showValue
          />
        </span>
      </div>

      {/* coordinate readout — grid primary, DDM secondary, datum explicit (radio-speakable) */}
      <div className="rounded-sm bg-surface-2 p-2">
        <div data-testid="coord-grid" className="text-base text-text-hi">{coord.grid}</div>
        <div data-testid="coord-geographic" className="text-text-mid">{coord.geographic}</div>
        <div className="text-text-lo">
          R95 {contact.r95_m.toFixed(0)} m · WGS84 · <span data-testid="coord-datum">{coord.datum}</span>
        </div>
      </div>

      {/* never-hidden trust fields */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-text-lo">
        <span>age {formatAge(contact.age_frames / FRAME_RATE)}</span>
        <span>{contact.convergence_state === "STABLE" ? "STABLE" : "CONVERGING"}</span>
        {contact.heading_limited && <span className="text-st-stale">⚠ heading-limited</span>}
        {stale && <span className="text-st-stale">⚠ telemetry STALE</span>}
        {contact.moving_suspected && <span className="text-st-caution">moving?</span>}
      </div>

      {/* command block: the current clearance state, then one primary verb + the secondary
          verbs grouped together (the state chip is NOT in the verb row — it's a status, not
          an action; keeping it separate kills the "fourth button" ambiguity). */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-1 text-text-lo">
          <Crosshair size={12} aria-hidden /> clearance:{" "}
          <span className="text-text-mid">{clearance.replace("_", " ")}</span>
        </div>
        <button
          onClick={advance}
          className="flex h-[var(--hit-primary)] items-center justify-center gap-2 rounded-sm bg-blue-core font-medium text-text-hi outline-none hover:brightness-110 focus-visible:shadow-focus"
        >
          <Send size={14} aria-hidden /> {primaryVerb(clearance)}
        </button>
        <div className="flex gap-4 text-text-lo">
          <button
            aria-label="undo"
            onClick={undo}
            className="flex h-[var(--hit-min)] items-center gap-1 rounded-sm px-2 outline-none hover:text-text-hi focus-visible:shadow-focus"
          >
            <RotateCcw size={13} aria-hidden /> undo
          </button>
          {/* operator-promote → on-demand Fuse (M6): localize THIS contact now, even if not
              auto-confirmed. The service returns a refined record over the same WS. */}
          <button
            aria-label="promote to fuse"
            onClick={() => commandSink.promote(contact.track_id)}
            className="flex h-[var(--hit-min)] items-center gap-1 rounded-sm px-2 text-blue-bright outline-none hover:text-blue-core focus-visible:shadow-focus"
          >
            <ArrowUpFromDot size={13} aria-hidden /> promote → fuse
          </button>
        </div>
      </div>
    </div>
  );
}
