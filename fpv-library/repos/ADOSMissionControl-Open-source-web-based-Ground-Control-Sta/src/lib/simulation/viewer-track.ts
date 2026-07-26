/**
 * @module simulation/viewer-track
 * @description Viewer-level track descriptor for the 3D simulation. A ViewerTrack
 * pairs a source tier (kinematic / replay / live) with the Cesium time-sampled
 * position + heading the viewer renders for it. The simulation viewer holds a
 * `tracks[]` array so several tracks — a planned kinematic path plus, later, a
 * recorded replay or a live feed — can render under one shared clock. The kinematic
 * track wraps the unchanged `buildSampledProperties` output and passes it through
 * verbatim, so a single-track set renders identically to the prior single-path viewer.
 * @license GPL-3.0-only
 */

import type { SampledProperties } from "@/lib/build-sampled-properties";
import type { TrackSourceTier } from "./sampled-track-source";

/**
 * A renderable track in the simulation viewer: a source tier plus the Cesium
 * time-sampled properties driven by the shared clock.
 */
export interface ViewerTrack {
  /** Stable identity within a tracks[] set — Cesium entity keys derive from it. */
  id: string;
  sourceTier: TrackSourceTier;
  /** Cesium time-sampled position/heading for this track, or null when unresolved. */
  sampled: SampledProperties | null;
  /** True when this track's sampled positions are already absolute (skip terrain adjust). */
  useAbsoluteAlt: boolean;
  /** Whether this track's drone entity should be shown. */
  visible: boolean;
}

/**
 * Wrap the planned-path {@link SampledProperties} as the primary kinematic track.
 * `sampled` is passed through unchanged (same object identity), so the kinematic
 * rendering stays byte-identical to the prior single-path viewer — this helper only
 * attaches the tier + per-track flags.
 */
export function makeKinematicViewerTrack(
  sampled: SampledProperties | null,
  useAbsoluteAlt: boolean,
  visible: boolean,
): ViewerTrack {
  return { id: "kinematic", sourceTier: "kinematic", sampled, useAbsoluteAlt, visible };
}
