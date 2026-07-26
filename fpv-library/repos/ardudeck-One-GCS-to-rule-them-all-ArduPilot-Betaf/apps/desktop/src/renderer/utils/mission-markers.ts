import { MAV_CMD, type MissionItem } from '../../shared/mission-types';

// Above this many located waypoints a mission is treated as large/auto-
// generated (surveys, corridors, imported KMLs): plain nav waypoints are
// dropped from the map and only operationally meaningful markers keep a labeled
// pin. Below it, every located waypoint keeps its numbered pin. A pilot can't
// act on "waypoint 18020" - it's an array index, not a place - and thousands of
// them stack into an unreadable cluster, so the flight path carries the route
// and the pins carry the decisions.
export const SEMANTIC_MARKER_THRESHOLD = 100;

// Commands worth a labeled pin even on a large mission. Plain NAV_WAYPOINT /
// NAV_SPLINE_WAYPOINT (the bulk of a survey) are intentionally absent: their
// sequence number is meaningless to a pilot and the path already shows them.
export function isKeyCommand(cmd: number): boolean {
  switch (cmd) {
    case MAV_CMD.NAV_TAKEOFF:
    case MAV_CMD.NAV_VTOL_TAKEOFF:
    case MAV_CMD.NAV_LAND:
    case MAV_CMD.NAV_VTOL_LAND:
    case MAV_CMD.NAV_RETURN_TO_LAUNCH:
    case MAV_CMD.NAV_LOITER_UNLIM:
    case MAV_CMD.NAV_LOITER_TIME:
    case MAV_CMD.NAV_LOITER_TURNS:
    case MAV_CMD.NAV_LOITER_TO_ALT:
    case MAV_CMD.NAV_PAYLOAD_PLACE:
    case MAV_CMD.DO_SET_ROI:
    case MAV_CMD.DO_SET_ROI_LOCATION:
      return true;
    default:
      return false;
  }
}

export type MarkerRole = 'current' | 'start' | 'end' | 'key';

export interface KeyMarker {
  wp: MissionItem;
  role: MarkerRole;
}

export interface MissionMarkerSplit {
  /** Waypoints that keep a labeled pin. */
  pins: KeyMarker[];
  /** Bulk waypoints suppressed in semantic mode. Empty when the mission is small. */
  bulk: MissionItem[];
  /** True when plain waypoints were collapsed away (large mission). */
  semantic: boolean;
}

/**
 * Split located waypoints into labeled pins vs suppressed bulk.
 *
 * Small missions return every waypoint as a 'key' pin so the caller renders its
 * usual numbered marker. Large missions return only the live target, the
 * route's start/end, and meaningful commands (launch, landing, loiter/turns,
 * ROI) - everything else lands in `bulk` for the caller to drop or draw quietly.
 *
 * Role precedence: current target > key command > start > end. A command keeps
 * its own glyph at the endpoints (e.g. a TAKEOFF first item shows the takeoff
 * marker, not "START"); only plain endpoints get START/END.
 */
export function splitMissionMarkers(
  located: MissionItem[],
  currentSeq: number | null,
): MissionMarkerSplit {
  if (located.length <= SEMANTIC_MARKER_THRESHOLD) {
    return {
      pins: located.map((wp) => ({ wp, role: 'key' as const })),
      bulk: [],
      semantic: false,
    };
  }

  const firstSeq = located[0]?.seq;
  const lastSeq = located[located.length - 1]?.seq;
  const pins: KeyMarker[] = [];
  const bulk: MissionItem[] = [];

  for (const wp of located) {
    let role: MarkerRole | null = null;
    if (wp.seq === currentSeq) role = 'current';
    else if (isKeyCommand(wp.command)) role = 'key';
    else if (wp.seq === firstSeq) role = 'start';
    else if (wp.seq === lastSeq) role = 'end';

    if (role) pins.push({ wp, role });
    else bulk.push(wp);
  }

  return { pins, bulk, semantic: true };
}
