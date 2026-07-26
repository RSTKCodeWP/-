/**
 * @module use-sim-camera
 * @description 4-mode camera state machine for simulation view.
 * Handles transitions between topdown, follow, orbit, and free camera modes.
 * Runs once per mode change, NOT per frame.
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import {
  Cartesian3,
  Cartographic,
  BoundingSphere,
  HeadingPitchRange,
  Math as CesiumMath,
  Matrix4,
  Transforms,
  type Viewer as CesiumViewer,
} from "cesium";
import type { Waypoint } from "@/lib/types";
import type { FlightPlan } from "@/lib/simulation-utils";
import { interpolatePosition } from "@/lib/simulation-utils";
import { useSimulationStore, type CameraMode } from "@/stores/simulation-store";

/**
 * Camera mode transition hook — positions camera on mode change.
 * Follow-camera per-frame tracking is handled by useSimClock's onTick.
 */
export function useSimCamera(
  viewer: CesiumViewer | null,
  waypoints: Waypoint[],
  flightPlan: FlightPlan,
  /** Terrain-resolved waypoint positions (absolute altitude). Use for accurate bounding. */
  resolvedWaypointPositions?: Cartesian3[]
): void {
  const cameraMode = useSimulationStore((s) => s.cameraMode);
  const cameraViewNonce = useSimulationStore((s) => s.cameraViewNonce);
  const prevModeRef = useRef<CameraMode>("orbit");
  // Tracks the last-seen reset-view nonce so the effect can tell a genuine
  // reset-view click apart from a mode/waypoint change. The nonce is monotonic,
  // so "did it change this run" — not "is it > 0" — is the right discriminator.
  const prevNonceRef = useRef(cameraViewNonce);
  const flightPlanRef = useRef(flightPlan);
  flightPlanRef.current = flightPlan;

  useEffect(() => {
    if (!viewer || viewer.isDestroyed() || waypoints.length === 0) return;

    const prev = prevModeRef.current;
    prevModeRef.current = cameraMode;
    const resetViewRequested = cameraViewNonce !== prevNonceRef.current;
    prevNonceRef.current = cameraViewNonce;

    // When leaving follow mode, unlock the camera transform so
    // ScreenSpaceCameraController (scroll/pan/rotate) works again
    if (prev === "follow" && cameraMode !== "follow") {
      viewer.camera.lookAtTransform(Matrix4.IDENTITY);
    }

    if (cameraMode === "topdown") {
      const positions = resolvedWaypointPositions
        ?? waypoints.map((wp) => Cartesian3.fromDegrees(wp.lon, wp.lat, wp.alt));
      const sphere = BoundingSphere.fromPoints(positions);
      const range = Math.max(sphere.radius * 3, 500);
      viewer.camera.flyToBoundingSphere(sphere, {
        duration: 0.8,
        offset: new HeadingPitchRange(0, CesiumMath.toRadians(-90), range),
      });
    } else if (cameraMode === "follow") {
      // Instant lookAtTransform setup — ScreenSpaceCameraController respects this
      const synced = useSimulationStore.getState().syncedPosition;
      let target: Cartesian3;
      let heading: number;
      if (synced) {
        // Use synced position from CesiumJS (already terrain-adjusted)
        const carto = Cartographic.fromDegrees(synced.lon, synced.lat);
        const terrainH = viewer.scene.globe.getHeight(carto) ?? 0;
        target = Cartesian3.fromDegrees(synced.lon, synced.lat, synced.altAgl + terrainH);
        heading = synced.heading;
      } else {
        const elapsed = useSimulationStore.getState().elapsed;
        const pos = interpolatePosition(flightPlanRef.current.segments, waypoints, elapsed);
        const carto = Cartographic.fromDegrees(pos.lon, pos.lat);
        const terrainH = viewer.scene.globe.getHeight(carto) ?? 0;
        target = Cartesian3.fromDegrees(pos.lon, pos.lat, pos.alt + terrainH);
        heading = pos.heading;
      }
      const transform = Transforms.eastNorthUpToFixedFrame(target);
      viewer.camera.lookAtTransform(
        transform,
        new HeadingPitchRange(
          CesiumMath.toRadians(heading),
          CesiumMath.toRadians(-30),
          200
        )
      );
    } else if (cameraMode === "orbit") {
      const positions = resolvedWaypointPositions
        ?? waypoints.map((wp) => Cartesian3.fromDegrees(wp.lon, wp.lat, wp.alt));
      const sphere = BoundingSphere.fromPoints(positions);
      viewer.camera.flyToBoundingSphere(sphere, {
        duration: 0.8,
        offset: new HeadingPitchRange(
          CesiumMath.toRadians(45),
          CesiumMath.toRadians(-45),
          Math.max(sphere.radius * 4, 800)
        ),
      });
    } else if (cameraMode === "free") {
      viewer.camera.lookAtTransform(Matrix4.IDENTITY);
      // On an explicit reset-view request, reframe the mission north-up so the
      // reset button is useful in free mode too (a bare identity transform
      // leaves the view exactly where it was). Only when the nonce actually
      // changed this run — entering free mode or a waypoint change must NOT
      // reframe, or free mode would keep snapping back to the overview.
      if (resetViewRequested) {
        const positions = resolvedWaypointPositions
          ?? waypoints.map((wp) => Cartesian3.fromDegrees(wp.lon, wp.lat, wp.alt));
        const sphere = BoundingSphere.fromPoints(positions);
        viewer.camera.flyToBoundingSphere(sphere, {
          duration: 0.6,
          offset: new HeadingPitchRange(
            0,
            CesiumMath.toRadians(-45),
            Math.max(sphere.radius * 4, 800)
          ),
        });
      }
    }
  }, [viewer, cameraMode, cameraViewNonce, waypoints, resolvedWaypointPositions]);
}
