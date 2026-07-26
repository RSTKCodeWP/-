/**
 * @module use-terrain-profile
 * @description Single producer of the debounced, abortable terrain-elevation
 * profile along a mission path. Extracted from TerrainProfileChart so the chart,
 * the along-leg terrain-clearance validator, and the red-collision-segment
 * renderers all read ONE profile (no duplicate Open-Elevation fetches). Returns
 * `status: "unavailable"` (not an empty profile) when the elevation data can't be
 * fetched, so callers show an honest offline state instead of a flat baseline.
 * @license GPL-3.0-only
 */
"use client";

import { useEffect, useRef, useState } from "react";
import type { Waypoint } from "@/lib/types";
import type { TerrainProfile } from "@/lib/terrain/types";
import { computeTerrainProfile } from "@/lib/terrain/terrain-profile";

export type TerrainProfileStatus = "idle" | "loading" | "ready" | "unavailable";

/**
 * Fetch the terrain profile for `waypoints` (debounced 500ms, previous request
 * aborted on change). `samplesPerSegment` controls along-leg density.
 */
export function useTerrainProfile(
  waypoints: Waypoint[],
  samplesPerSegment = 5,
): { profile: TerrainProfile | null; status: TerrainProfileStatus } {
  const [profile, setProfile] = useState<TerrainProfile | null>(null);
  const [status, setStatus] = useState<TerrainProfileStatus>("idle");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (waypoints.length < 2) {
      setProfile(null);
      setStatus("idle");
      return;
    }
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const timer = setTimeout(() => {
      setStatus("loading");
      computeTerrainProfile(waypoints, samplesPerSegment, controller.signal)
        .then((p) => {
          if (controller.signal.aborted) return;
          if (!p || p.points.length === 0) {
            setProfile(null);
            setStatus("unavailable");
          } else {
            setProfile(p);
            setStatus("ready");
          }
        })
        .catch((err) => {
          if ((err as Error).name === "AbortError") return;
          if (!controller.signal.aborted) {
            setProfile(null);
            setStatus("unavailable");
          }
        });
    }, 500);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [waypoints, samplesPerSegment]);

  return { profile, status };
}
