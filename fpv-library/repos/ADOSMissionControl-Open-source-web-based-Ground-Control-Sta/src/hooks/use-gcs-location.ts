/**
 * @module use-gcs-location
 * @description Lifecycle bridge between settings-store `locationEnabled` preference
 * and gcs-location-store runtime. Mount once in CommandShell.
 * @license GPL-3.0-only
 */

"use client";

import { useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { useGcsLocationStore } from "@/stores/gcs-location-store";

export function useGcsLocation() {
  const locationEnabled = useSettingsStore((s) => s.locationEnabled);
  const hasHydrated = useSettingsStore((s) => s._hasHydrated);
  const permission = useGcsLocationStore((s) => s.permission);

  useEffect(() => {
    if (!hasHydrated) return;

    if (locationEnabled) {
      useGcsLocationStore.getState().initLocation();
    } else {
      useGcsLocationStore.getState().stopWatching();
    }
  }, [locationEnabled, hasHydrated]);

  // Stop watching if permission gets externally revoked
  useEffect(() => {
    if (permission === "denied") {
      useGcsLocationStore.getState().stopWatching();
    }
  }, [permission]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      useGcsLocationStore.getState().stopWatching();
    };
  }, []);
}
