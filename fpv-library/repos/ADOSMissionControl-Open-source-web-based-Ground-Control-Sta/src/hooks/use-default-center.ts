/**
 * @module use-default-center
 * @description Returns the user's GPS position as map center if available,
 * otherwise falls back to Null Island (0, 0).
 * @license GPL-3.0-only
 */

import { useSettingsStore } from "@/stores/settings-store";
import { useGcsLocationStore } from "@/stores/gcs-location-store";
import { DEFAULT_CENTER } from "@/lib/map-constants";

export function useDefaultCenter(): [number, number] {
  const locationEnabled = useSettingsStore((s) => s.locationEnabled);
  const position = useGcsLocationStore((s) => s.position);
  if (locationEnabled && position) return [position.lat, position.lon];
  return DEFAULT_CENTER;
}
