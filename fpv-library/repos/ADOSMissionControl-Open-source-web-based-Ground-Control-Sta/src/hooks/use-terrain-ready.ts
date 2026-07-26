/**
 * @module use-terrain-ready
 * @description Tracks CesiumJS terrain provider readiness. Returns `isReady: true`
 * only when the globe has a real terrain provider (not the default EllipsoidTerrainProvider
 * which returns height=0 everywhere). Also exposes a `version` counter that increments
 * on every provider change, so dependents can re-resolve terrain data when the provider
 * upgrades (e.g. ArcGIS → Cesium World Terrain after Ion token arrives).
 * @license GPL-3.0-only
 */

"use client";

import { useState, useEffect } from "react";
import { EllipsoidTerrainProvider, type Viewer as CesiumViewer } from "cesium";

interface TerrainReadyState {
  /** True when the terrain provider is NOT the default flat ellipsoid. */
  isReady: boolean;
  /** Increments on every terrain provider change — use as effect dependency. */
  version: number;
}

/**
 * Hook that listens to `viewer.scene.globe.terrainProviderChanged` and
 * reports whether the current terrain provider can return real elevation data.
 */
export function useTerrainReady(viewer: CesiumViewer | null): TerrainReadyState {
  const [state, setState] = useState<TerrainReadyState>({
    isReady: false,
    version: 0,
  });

  useEffect(() => {
    if (!viewer || viewer.isDestroyed()) {
      setState({ isReady: false, version: 0 });
      return;
    }

    const globe = viewer.scene.globe;

    /** Check if the current provider is a real terrain source. */
    function check() {
      if (!viewer || viewer.isDestroyed()) return;
      const provider = globe.terrainProvider;
      const ready = !(provider instanceof EllipsoidTerrainProvider);
      setState((prev) => ({
        isReady: ready,
        version: prev.version + 1,
      }));
    }

    // Check immediately — terrain may already be loaded
    check();

    // Listen for provider swaps (ArcGIS load, Ion token upgrade, etc.)
    const removeListener = globe.terrainProviderChanged.addEventListener(check);

    // A provider swap may have fired between viewer construction and listener attach.
    // Re-check after a microtask + a frame to catch that race.
    queueMicrotask(check);
    const rafId = requestAnimationFrame(check);

    return () => {
      removeListener();
      cancelAnimationFrame(rafId);
    };
  }, [viewer]);

  return state;
}
