/**
 * @module sim-camera-modes
 * @description Shared camera-mode catalog for the simulation view. Single
 * source for the on-canvas camera cluster and the keyboard-shortcut hints so
 * the mode list, icons, and keys never drift.
 * @license GPL-3.0-only
 */

import { Grid2x2, Navigation, Orbit, Move3d, type LucideIcon } from "lucide-react";
import type { CameraMode } from "@/stores/simulation-store";

export interface CameraModeDef {
  id: CameraMode;
  /** Keyboard shortcut letter (mirrors use-simulation-keyboard). */
  key: string;
  icon: LucideIcon;
  /** i18n key under the `simulate` namespace. */
  labelKey: string;
}

export const CAMERA_MODES: CameraModeDef[] = [
  { id: "topdown", key: "T", icon: Grid2x2, labelKey: "cameraTopDown" },
  { id: "follow", key: "F", icon: Navigation, labelKey: "cameraFollow" },
  { id: "orbit", key: "O", icon: Orbit, labelKey: "cameraOrbit" },
  { id: "free", key: "X", icon: Move3d, labelKey: "cameraFree" },
];
