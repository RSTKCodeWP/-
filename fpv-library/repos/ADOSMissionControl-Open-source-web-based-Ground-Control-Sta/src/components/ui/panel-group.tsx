/**
 * @module PanelBand
 * @description Groups related planner right-panel sections under a labeled band
 * header (Setup / Build / Review). Purely presentational: it renders a small
 * uppercase band header above its children and never alters any child section's
 * own open/close behavior, so the existing controlled/uncontrolled
 * CollapsibleSections keep working unchanged.
 *
 * Panel-home convention for later planner features: authoring tools (patterns,
 * waypoints, geofence, transform, coverage/GSD) dock in the BUILD band; safety
 * and environment read-outs (terrain, validation, weather, energy) dock in the
 * REVIEW band; mission/aircraft defaults dock in SETUP. Map-anchored surfaces
 * (airspace, coverage, DEM) render as map overlays, not panel sections.
 * @license GPL-3.0-only
 */
"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelBandProps {
  /** The already-translated band title. */
  title: string;
  children: ReactNode;
  className?: string;
}

export function PanelBand({ title, children, className }: PanelBandProps) {
  return (
    <div className={className}>
      <div className="px-3 py-1.5 bg-bg-tertiary/40 border-b border-border-default">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-tertiary">
          {title}
        </span>
      </div>
      <div className={cn("flex flex-col")}>{children}</div>
    </div>
  );
}
