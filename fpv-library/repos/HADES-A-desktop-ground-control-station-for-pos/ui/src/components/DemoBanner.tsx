import { Info } from "lucide-react";
import { useState } from "react";

import { useProvenanceStore } from "../store/provenance";

/* The demo-mode provenance banner (Phase 6 / adversarial demo-craft panel R5). Shown ONLY when
 * the static demo replays a baked `mission.json` (provenance set); invisible in the live app and
 * the synthetic-mock fallback.
 *
 * Honesty rules it encodes:
 *  - Color = off-ramp VIOLET-SLATE (`--st-stale`), NOT magenta. A demo is an epistemic caveat
 *    ("this is not live operational data"), not a system-integrity failure (magenta is reserved
 *    for link-lost, the P0 life-safety rule). Using the right semantic color is part of not
 *    looking like AI slop.
 *  - It names EXACTLY which numbers are real vs scripted: the scene + drone pose are scripted,
 *    every pin / ellipse / confidence is live localizer output run against known ground truth.
 *    The real median error in meters rides in the banner — the honesty caveat as a flex.
 *  - It states plainly there is no live feed, so no coordinator mistakes it for an active
 *    mission. Full provenance (incl. "real footage lands later") sits behind a [details]
 *    disclosure to keep the strip terse. */

export function DemoBanner() {
  const provenance = useProvenanceStore((s) => s.provenance);
  const [open, setOpen] = useState(false);
  if (!provenance) return null;

  const err = provenance.median_error_m;
  return (
    <div
      data-testid="demo-banner"
      className="flex w-full flex-col gap-1 border-b border-st-stale/20 bg-st-stale/[0.07] px-5 py-2 font-mono text-xs text-st-stale"
      style={{ zIndex: "var(--z-status-strip)" }}
    >
      <div className="flex items-center gap-3">
        <Info size={14} aria-hidden className="shrink-0" />
        <span className="font-ui font-bold uppercase tracking-[0.08em] text-text-hi">Demo Mode</span>
        <span className="text-text-lo">
          synthetic scene, real pipeline — pins, ellipses, and confidence are live HADES
          localizer output against known ground truth (median error {err.toFixed(1)} m). No live
          feed, no operator on shift.
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-st-stale underline-offset-2 hover:underline focus:outline-none focus:ring-1 focus:ring-st-stale"
          aria-expanded={open}
        >
          {open ? "hide details" : "details"}
        </button>
      </div>
      {open && (
        <p className="max-w-3xl pl-[26px] leading-snug text-text-lo">{provenance.note}</p>
      )}
    </div>
  );
}
