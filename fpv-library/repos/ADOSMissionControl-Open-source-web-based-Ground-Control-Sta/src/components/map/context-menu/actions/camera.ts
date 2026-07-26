/**
 * @module map/context-menu/actions/camera
 * @description Camera and gimbal action handlers: ROI point/clear, shutter trigger.
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import type { MenuPosition } from "../types";

interface CameraArgs {
  protocol: DroneProtocol | null;
  menuPos: MenuPosition;
  relativeAlt: number | undefined;
}

export function handlePointCamera({ protocol, menuPos, relativeAlt }: CameraArgs): void {
  if (!protocol) return;
  if (protocol.setRoiLocation) {
    protocol.setRoiLocation(menuPos.lat, menuPos.lon, relativeAlt ?? 0);
  } else if (protocol.setGimbalROI) {
    protocol.setGimbalROI(menuPos.lat, menuPos.lon, relativeAlt ?? 0);
  }
}

export function handleClearRoi(protocol: DroneProtocol | null): void {
  if (protocol?.clearRoi) protocol.clearRoi();
}

export function handleTriggerCamera(protocol: DroneProtocol | null): void {
  if (protocol) protocol.cameraTrigger();
}
