"use client";

/**
 * @module VisionModelRegistry
 * @description Thin shell over {@link ModelPicker} (mode="full") for a single
 * drone's Vision tab. The picker owns the merged registry + installed + custom
 * list, the board-fit filter, download-on-select, set-active, and the custom
 * upload; this component exists to keep the Vision tab's import surface stable.
 *
 * @license GPL-3.0-only
 */

import { ModelPicker } from "./ModelPicker";

interface VisionModelRegistryProps {
  /** Drone whose engine detector this surface manages (Rule 39 LAN routing). */
  droneId: string;
}

export function VisionModelRegistry({ droneId }: VisionModelRegistryProps) {
  return <ModelPicker droneId={droneId} mode="full" />;
}
