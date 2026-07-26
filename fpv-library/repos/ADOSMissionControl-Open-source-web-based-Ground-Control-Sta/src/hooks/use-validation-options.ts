/**
 * @module use-validation-options
 * @description Single source of truth for building mission `ValidationOptions`
 * from the geofence + rally stores, shared by the Plan tab's ValidationPanel and
 * the Simulate tab's banner so both surfaces gate the fence identically (no
 * phantom errors from stale inactive geometry) and both enforce zones + rally.
 * @license GPL-3.0-only
 */
"use client";

import { useMemo } from "react";
import { useGeofenceStore } from "@/stores/geofence-store";
import { useRallyStore } from "@/stores/rally-store";
import type { ValidationOptions } from "@/lib/validation/mission-validator";

export function useValidationOptions(): ValidationOptions | undefined {
  const enabled = useGeofenceStore((s) => s.enabled);
  const fenceType = useGeofenceStore((s) => s.fenceType);
  const maxAltitude = useGeofenceStore((s) => s.maxAltitude);
  const minAltitude = useGeofenceStore((s) => s.minAltitude);
  const polygonPoints = useGeofenceStore((s) => s.polygonPoints);
  const circleCenter = useGeofenceStore((s) => s.circleCenter);
  const circleRadius = useGeofenceStore((s) => s.circleRadius);
  const zones = useGeofenceStore((s) => s.zones);
  const rallyPoints = useRallyStore((s) => s.points);

  return useMemo(() => {
    // Primary fence geometry is gated on `enabled` and the active `fenceType`, so
    // switching fence type never leaves stale geometry driving a false breach.
    // Multi-zone fences are explicit keep-in/keep-out areas — enforced whenever
    // present, independent of the legacy primary-fence toggle.
    const geofence: NonNullable<ValidationOptions["geofence"]> = {};
    if (enabled) {
      if (maxAltitude > 0) geofence.maxAltitude = maxAltitude;
      if (minAltitude > 0) geofence.minAltitude = minAltitude;
      if (fenceType === "polygon" && polygonPoints.length >= 3) geofence.polygonPoints = polygonPoints;
      if (fenceType === "circle" && circleCenter) {
        geofence.circleCenter = circleCenter;
        geofence.circleRadius = circleRadius;
      }
    }
    if (zones.length > 0) geofence.zones = zones;

    const hasFence = Object.keys(geofence).length > 0;
    const rally = rallyPoints.length > 0 ? rallyPoints : undefined;
    if (!hasFence && !rally) return undefined;
    return {
      geofence: hasFence ? geofence : undefined,
      rally,
    };
  }, [enabled, fenceType, maxAltitude, minAltitude, polygonPoints, circleCenter, circleRadius, zones, rallyPoints]);
}
