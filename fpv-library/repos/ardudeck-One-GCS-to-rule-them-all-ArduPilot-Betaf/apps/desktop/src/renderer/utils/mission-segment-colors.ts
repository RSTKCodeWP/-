/**
 * Shared segment color logic for mission path visualization.
 * Used by both MissionMapPanel (map lines) and WaypointTablePanel (sidebar indicators).
 */
import { MAV_CMD, isNavigationCommand, commandHasLocation, type MissionItem } from '../../shared/mission-types';

export const SEGMENT_COLORS = {
  default: '#3b82f6',    // Blue
  camera: '#f59e0b',     // Amber
  roi: '#a855f7',        // Purple
  speed: '#06b6d4',      // Cyan
  land: '#ef4444',       // Red
  rth: '#f97316',        // Orange
} as const;

/** Determine segment color from state flags and the target waypoint command */
export function getSegmentColor(
  targetCmd: number,
  cameraActive: boolean,
  roiActive: boolean,
  speedOverride: boolean,
): string {
  if (targetCmd === MAV_CMD.NAV_LAND || targetCmd === MAV_CMD.NAV_VTOL_LAND) return SEGMENT_COLORS.land;
  if (targetCmd === MAV_CMD.NAV_RETURN_TO_LAUNCH) return SEGMENT_COLORS.rth;
  if (cameraActive) return SEGMENT_COLORS.camera;
  if (roiActive) return SEGMENT_COLORS.roi;
  if (speedOverride) return SEGMENT_COLORS.speed;
  return SEGMENT_COLORS.default;
}

/**
 * Compute segment color for every mission item.
 * Returns Map<seq, hexColor> — nav waypoints get the incoming segment color,
 * DO_* children get the color of the segment they influence.
 */
export function computeItemColors(allItems: MissionItem[]): Map<number, string> {
  const colorMap = new Map<number, string>();

  const navWaypoints = allItems.filter(
    item => isNavigationCommand(item.command) && commandHasLocation(item.command),
  );

  if (navWaypoints.length === 0) return colorMap;

  let cameraActive = false;
  let roiActive = false;
  let speedOverride = false;

  // Single pass over all items in seq order (the old version re-scanned every
  // item for every nav pair — O(n²) — which froze the map and the waypoint
  // table on large 20k+ survey missions). DO_* commands update the flags and
  // are buffered until the next located waypoint, which colors them and itself.
  let prevNavSeen = false;
  let pendingChildSeqs: number[] = [];

  for (const item of allItems) {
    const isLocatedNav = isNavigationCommand(item.command) && commandHasLocation(item.command);

    if (isLocatedNav) {
      if (!prevNavSeen) {
        // First nav waypoint = default blue (no incoming segment).
        colorMap.set(item.seq, SEGMENT_COLORS.default);
        prevNavSeen = true;
      } else {
        const color = getSegmentColor(item.command, cameraActive, roiActive, speedOverride);
        for (const seq of pendingChildSeqs) colorMap.set(seq, color);
        colorMap.set(item.seq, color);
      }
      pendingChildSeqs = [];
      continue;
    }

    // Other nav commands (e.g. RTL) carry no segment color. DO_* before the
    // first located waypoint are ignored, matching the original windowing.
    if (isNavigationCommand(item.command)) continue;
    if (!prevNavSeen) continue;

    switch (item.command) {
      case MAV_CMD.DO_SET_CAM_TRIGG_DIST:
      case MAV_CMD.DO_SET_CAM_TRIGG_INTERVAL:
        cameraActive = item.param1 > 0;
        break;
      case MAV_CMD.IMAGE_START_CAPTURE:
        cameraActive = true;
        break;
      case MAV_CMD.IMAGE_STOP_CAPTURE:
        cameraActive = false;
        break;
      case MAV_CMD.DO_SET_ROI:
      case MAV_CMD.DO_SET_ROI_LOCATION:
        roiActive = true;
        break;
      case MAV_CMD.DO_SET_ROI_NONE:
        roiActive = false;
        break;
      case MAV_CMD.DO_CHANGE_SPEED:
        speedOverride = item.param2 > 0;
        break;
    }

    pendingChildSeqs.push(item.seq);
  }

  return colorMap;
}
