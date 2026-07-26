/**
 * @module mission-io-formats
 * @description Import/export for .waypoints and .plan file formats.
 * @license GPL-3.0-only
 */

import type { AltitudeFrame, Waypoint, WaypointCommand } from "@/lib/types";
import type { GeofenceSnapshot, FenceZone } from "@/stores/geofence-store";
import type { RallyPoint } from "@/stores/rally-store";
import { flattenForSerialization, foldLegacyWaypoints } from "@/lib/mission/mission-expand";

/**
 * MAV_FRAME numbers used for waypoint altitude reference.
 * - 0  = MAV_FRAME_GLOBAL          (absolute altitude, MSL)
 * - 3  = MAV_FRAME_GLOBAL_RELATIVE_ALT (relative to home, AGL)
 * - 10 = MAV_FRAME_GLOBAL_TERRAIN_ALT  (above terrain)
 */
const FRAME_GLOBAL = 0;
const FRAME_RELATIVE = 3;
const FRAME_TERRAIN = 10;

/** Mission default frame applied when a waypoint carries no explicit frame. */
const DEFAULT_FRAME: AltitudeFrame = "relative";

/** Map an altitude reference frame to its MAV_FRAME number. */
export function frameToMav(frame: AltitudeFrame | undefined): number {
  switch (frame ?? DEFAULT_FRAME) {
    case "absolute":
      return FRAME_GLOBAL;
    case "terrain":
      return FRAME_TERRAIN;
    case "relative":
    default:
      return FRAME_RELATIVE;
  }
}

/** Map a MAV_FRAME number back to an altitude reference frame. */
function mavToFrame(mav: number | undefined): AltitudeFrame {
  switch (mav) {
    case FRAME_GLOBAL:
      return "absolute";
    case FRAME_TERRAIN:
      return "terrain";
    case FRAME_RELATIVE:
    default:
      return "relative";
  }
}

/** MAVLink command string -> number mapping. */
export const cmdMap: Record<WaypointCommand, number> = {
  WAYPOINT: 16, SPLINE_WAYPOINT: 82, LOITER: 17, LOITER_TURNS: 18, LOITER_TIME: 19,
  RTL: 20, LAND: 21, TAKEOFF: 22, ROI: 201, DO_SET_SPEED: 178,
  DO_SET_CAM_TRIGG: 206, DO_DIGICAM: 203, DO_JUMP: 177, DELAY: 112,
  CONDITION_YAW: 115, DO_SET_SERVO: 183, DO_FENCE_ENABLE: 207,
  DO_MOUNT_CONTROL: 205, DO_GRIPPER: 211, DO_WINCH: 212,
  NAV_PAYLOAD_PLACE: 94, CONDITION_DISTANCE: 114, DO_SET_HOME: 179,
  DO_AUX_FUNCTION: 218, VTOL_TAKEOFF: 84, VTOL_LAND: 85,
  DO_SET_ROI_NONE: 197,
  DO_LAND_START: 189,
};

/** MAVLink command number -> string mapping. */
export const reverseCmd: Record<number, WaypointCommand> = Object.fromEntries(
  Object.entries(cmdMap).map(([k, v]) => [v, k as WaypointCommand])
) as Record<number, WaypointCommand>;

// ── .waypoints Export (ArduPilot / Mission Planner format) ───

/**
 * Export waypoints as a `.waypoints` file (QGC WPL 110 format).
 * Tab-separated plain text compatible with Mission Planner and ArduPilot.
 */
export function exportWaypointsFormat(waypoints: Waypoint[], name: string): void {
  const lines: string[] = ["QGC WPL 110"];

  // Flatten attached actions into sibling rows so external tools see them.
  const flat = flattenForSerialization(waypoints);
  const home = flat[0];
  lines.push(
    `0\t1\t0\t16\t0\t0\t0\t0\t${home?.lat ?? 0}\t${home?.lon ?? 0}\t0\t1`
  );

  flat.forEach((wp, i) => {
    const cmd = cmdMap[wp.command ?? "WAYPOINT"] ?? 16;
    const frame = frameToMav(wp.frame);
    const p1 = wp.holdTime ?? wp.param1 ?? 0;
    const p2 = wp.param2 ?? 0;
    const p3 = wp.param3 ?? 0;
    const p4 = 0;
    lines.push(
      `${i + 1}\t0\t${frame}\t${cmd}\t${p1}\t${p2}\t${p3}\t${p4}\t${wp.lat}\t${wp.lon}\t${wp.alt}\t1`
    );
  });

  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name || "mission"}.waypoints`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── .waypoints Import ────────────────────────────────────────

/** Parse a `.waypoints` (QGC WPL 110) file into Waypoint array. */
export function parseWaypointsFile(text: string): Waypoint[] {
  const lines = text.trim().split("\n");
  if (!lines[0]?.startsWith("QGC WPL")) {
    throw new Error("Invalid .waypoints file — missing QGC WPL header");
  }

  const flat: Waypoint[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].trim().split("\t");
    if (cols.length < 12) continue;

    const seq = parseInt(cols[0]);
    if (seq === 0) continue;

    const frameNum = parseInt(cols[2]);
    const frame = mavToFrame(Number.isFinite(frameNum) ? frameNum : undefined);
    const cmdNum = parseInt(cols[3]);
    const command = reverseCmd[cmdNum] ?? "WAYPOINT";
    const lat = parseFloat(cols[8]);
    const lon = parseFloat(cols[9]);
    const alt = parseFloat(cols[10]);
    // Skip malformed rows: a non-numeric lat/lon would otherwise create a
    // waypoint at NaN,NaN that renders nowhere and fails validation silently.
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const safeAlt = Number.isFinite(alt) ? alt : 0;
    const p1 = parseFloat(cols[4]) || undefined;
    const p2 = parseFloat(cols[5]) || undefined;
    const p3 = parseFloat(cols[6]) || undefined;

    flat.push({
      id: Math.random().toString(36).substring(2, 10),
      lat, lon, alt: safeAlt,
      command,
      frame,
      holdTime: (command === "LOITER" || command === "LOITER_TIME") ? p1 : undefined,
      param1: (command !== "LOITER" && command !== "LOITER_TIME") ? p1 : undefined,
      param2: p2,
      param3: p3,
    });
  }

  // Fold any action-command rows into the navigation waypoint they follow.
  return foldLegacyWaypoints(flat);
}

// ── Extra plan payload (fence + rally) carried alongside waypoints ──

/** Optional fence + rally payload serialized into / parsed out of a `.plan`. */
export interface PlanExtras {
  geofence?: GeofenceSnapshot;
  rally?: RallyPoint[];
}

/** Result of parsing a `.plan` file: waypoints plus any fence / rally it carried. */
export interface ParsedPlan {
  waypoints: Waypoint[];
  geofence?: GeofenceSnapshot;
  rally?: RallyPoint[];
}

// ── .plan Export (QGroundControl JSON format) ────────────────

interface QGCFenceCircleEntry {
  inclusion: boolean;
  version: 1;
  circle: { center: [number, number]; radius: number };
}

interface QGCFencePolygonEntry {
  inclusion: boolean;
  version: 1;
  polygon: Array<[number, number]>;
}

/** Serialize the operator geofence into the .plan geoFence block. */
function geofenceToQGC(snapshot: GeofenceSnapshot | undefined): {
  circles: QGCFenceCircleEntry[];
  polygons: QGCFencePolygonEntry[];
  version: 2;
} {
  const circles: QGCFenceCircleEntry[] = [];
  const polygons: QGCFencePolygonEntry[] = [];

  if (snapshot) {
    // Multi-zone inclusion / exclusion fences.
    for (const z of snapshot.zones) {
      const inclusion = z.role === "inclusion";
      if (z.type === "circle" && z.circleCenter) {
        circles.push({
          inclusion,
          version: 1,
          circle: { center: [z.circleCenter[0], z.circleCenter[1]], radius: z.circleRadius },
        });
      } else if (z.type === "polygon" && z.polygonPoints.length >= 3) {
        polygons.push({
          inclusion,
          version: 1,
          polygon: z.polygonPoints.map(([lat, lon]) => [lat, lon] as [number, number]),
        });
      }
    }

    // Legacy single top-level fence (inclusion by definition — must stay inside).
    if (snapshot.enabled) {
      if (snapshot.fenceType === "circle" && snapshot.circleCenter) {
        circles.push({
          inclusion: true,
          version: 1,
          circle: {
            center: [snapshot.circleCenter[0], snapshot.circleCenter[1]],
            radius: snapshot.circleRadius,
          },
        });
      } else if (snapshot.fenceType === "polygon" && snapshot.polygonPoints.length >= 3) {
        polygons.push({
          inclusion: true,
          version: 1,
          polygon: snapshot.polygonPoints.map(([lat, lon]) => [lat, lon] as [number, number]),
        });
      }
    }
  }

  return { circles, polygons, version: 2 };
}

/** Serialize rally points into the .plan rallyPoints block ([lat, lon, alt] triples). */
function rallyToQGC(rally: RallyPoint[] | undefined): {
  points: Array<[number, number, number]>;
  version: 2;
} {
  const points: Array<[number, number, number]> = (rally ?? []).map((p) => [p.lat, p.lon, p.alt]);
  return { points, version: 2 };
}

/**
 * Export waypoints as a `.plan` file (QGC JSON format). When `extras` carries a
 * geofence and/or rally points they are serialized into the geoFence and
 * rallyPoints blocks so the plan round-trips the full mission, not just the path.
 */
export function exportQGCPlan(
  waypoints: Waypoint[],
  name: string,
  metadata?: { cruiseSpeed?: number; vehicleType?: number },
  extras?: PlanExtras,
): void {
  // Flatten attached actions into sibling SimpleItems, the way QGC stores DO
  // commands, so a plan round-trips its per-waypoint actions.
  const flat = flattenForSerialization(waypoints);
  const home = flat[0];
  const items = flat.map((wp, i) => ({
    autoContinue: true,
    command: cmdMap[wp.command ?? "WAYPOINT"] ?? 16,
    doJumpId: i + 1,
    frame: frameToMav(wp.frame),
    params: [
      wp.holdTime ?? wp.param1 ?? 0,
      wp.param2 ?? 0,
      wp.param3 ?? 0,
      0,
      wp.lat,
      wp.lon,
      wp.alt,
    ],
    type: "SimpleItem",
  }));

  const plan = {
    fileType: "Plan",
    groundStation: "Altnautica Command",
    version: 1,
    mission: {
      cruiseSpeed: metadata?.cruiseSpeed ?? 15,
      firmwareType: 3,
      items,
      plannedHomePosition: [home?.lat ?? 0, home?.lon ?? 0, 0],
      vehicleType: metadata?.vehicleType ?? 2,
      version: 2,
    },
    geoFence: geofenceToQGC(extras?.geofence),
    rallyPoints: rallyToQGC(extras?.rally),
  };

  const blob = new Blob([JSON.stringify(plan, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name || "mission"}.plan`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── .plan Import ─────────────────────────────────────────────

/** Minimal typed views of the QGC .plan structures we read. */
interface QGCMissionItem {
  type?: string;
  command?: number;
  frame?: number;
  params?: number[];
  complexItemType?: string;
  TransectStyleComplexItem?: QGCTransectStyle;
  // Present when the item itself is a TransectStyleComplexItem (transect fields inline).
  Items?: QGCMissionItem[];
  VisualTransectPoints?: Array<[number, number]>;
}

interface QGCTransectStyle {
  Items?: QGCMissionItem[];
  VisualTransectPoints?: Array<[number, number]>;
}

interface QGCGeoFence {
  circles?: Array<{ inclusion?: boolean; circle?: { center?: [number, number]; radius?: number } }>;
  polygons?: Array<{ inclusion?: boolean; polygon?: Array<[number, number]> }>;
}

interface QGCPlanFile {
  fileType?: string;
  mission?: { items?: QGCMissionItem[] };
  geoFence?: QGCGeoFence;
  rallyPoints?: { points?: Array<[number, number, number]> };
}

let importZoneCounter = 0;
function nextImportZoneId(): string {
  return `fence-import-${++importZoneCounter}`;
}

let importRallyCounter = 0;
function nextImportRallyId(): string {
  return `rally-import-${++importRallyCounter}`;
}

/** Convert one QGC SimpleItem into a Waypoint (shared by top-level items and expanded transects). */
function simpleItemToWaypoint(item: QGCMissionItem): Waypoint {
  const cmdNum = item.command ?? 16;
  const command = reverseCmd[cmdNum] ?? "WAYPOINT";
  const frame = mavToFrame(typeof item.frame === "number" ? item.frame : undefined);
  const params = item.params ?? [];
  const lat = params[4] ?? 0;
  const lon = params[5] ?? 0;
  const alt = params[6] ?? 0;
  const p1 = params[0] || undefined;
  const p2 = params[1] || undefined;
  const p3 = params[2] || undefined;

  return {
    id: Math.random().toString(36).substring(2, 10),
    lat, lon, alt,
    command,
    frame,
    holdTime: (command === "LOITER" || command === "LOITER_TIME") ? p1 : undefined,
    param1: (command !== "LOITER" && command !== "LOITER_TIME") ? p1 : undefined,
    param2: p2,
    param3: p3,
  };
}

/**
 * Expand a single mission item into waypoints. SimpleItems map 1:1; a
 * ComplexItem / TransectStyleComplexItem (survey / corridor / structure grid)
 * is expanded from its embedded transect items or coordinates. A complex item
 * that carries no expandable geometry throws rather than being silently dropped.
 */
function expandPlanItem(item: QGCMissionItem, out: Waypoint[]): void {
  if (item.type === "SimpleItem") {
    out.push(simpleItemToWaypoint(item));
    return;
  }

  if (item.type === "ComplexItem" || item.type === "TransectStyleComplexItem") {
    const transect =
      item.TransectStyleComplexItem ??
      (item.type === "TransectStyleComplexItem" ? item : undefined);

    const embedded = transect?.Items;
    if (Array.isArray(embedded) && embedded.length > 0) {
      for (const sub of embedded) expandPlanItem(sub, out);
      return;
    }

    const visual = transect?.VisualTransectPoints ?? item.VisualTransectPoints;
    if (Array.isArray(visual) && visual.length > 0) {
      for (const pt of visual) {
        if (Array.isArray(pt) && pt.length >= 2 && Number.isFinite(pt[0]) && Number.isFinite(pt[1])) {
          out.push({
            id: Math.random().toString(36).substring(2, 10),
            lat: pt[0], lon: pt[1], alt: 0,
            command: "WAYPOINT",
            frame: DEFAULT_FRAME,
          });
        }
      }
      return;
    }

    throw new Error(
      `Cannot expand complex mission item "${item.complexItemType ?? item.type}" — no embedded transect items or coordinates found`,
    );
  }

  // Unrecognized non-simple, non-complex item types are skipped.
}

/** Parse the .plan geoFence block into a GeofenceSnapshot (inclusion / exclusion zones). */
function parseQGCGeoFence(geoFence: QGCGeoFence | undefined): GeofenceSnapshot | undefined {
  if (!geoFence) return undefined;

  const zones: FenceZone[] = [];

  for (const c of geoFence.circles ?? []) {
    const center = c?.circle?.center;
    const radius = c?.circle?.radius;
    if (
      Array.isArray(center) && center.length >= 2 &&
      Number.isFinite(center[0]) && Number.isFinite(center[1]) &&
      typeof radius === "number" && Number.isFinite(radius)
    ) {
      zones.push({
        id: nextImportZoneId(),
        role: c.inclusion === false ? "exclusion" : "inclusion",
        type: "circle",
        polygonPoints: [],
        circleCenter: [center[0], center[1]],
        circleRadius: radius,
      });
    }
  }

  for (const p of geoFence.polygons ?? []) {
    const poly = p?.polygon;
    if (Array.isArray(poly)) {
      const points = poly
        .filter((pt) => Array.isArray(pt) && pt.length >= 2 && Number.isFinite(pt[0]) && Number.isFinite(pt[1]))
        .map((pt) => [pt[0], pt[1]] as [number, number]);
      if (points.length >= 3) {
        zones.push({
          id: nextImportZoneId(),
          role: p.inclusion === false ? "exclusion" : "inclusion",
          type: "polygon",
          polygonPoints: points,
          circleCenter: null,
          circleRadius: 0,
        });
      }
    }
  }

  if (zones.length === 0) return undefined;

  return {
    enabled: true,
    fenceType: zones[0].type,
    maxAltitude: 120,
    minAltitude: 0,
    breachAction: "RTL",
    circleCenter: null,
    circleRadius: 200,
    polygonPoints: [],
    zones,
  };
}

/** Parse the .plan rallyPoints block into RallyPoint[]. */
function parseQGCRally(rallyPoints: QGCPlanFile["rallyPoints"]): RallyPoint[] | undefined {
  const raw = rallyPoints?.points;
  if (!Array.isArray(raw)) return undefined;

  const points: RallyPoint[] = [];
  for (const pt of raw) {
    if (Array.isArray(pt) && pt.length >= 2 && Number.isFinite(pt[0]) && Number.isFinite(pt[1])) {
      const alt = pt[2];
      points.push({
        id: nextImportRallyId(),
        lat: pt[0],
        lon: pt[1],
        alt: typeof alt === "number" && Number.isFinite(alt) ? alt : 0,
      });
    }
  }

  return points.length > 0 ? points : undefined;
}

/**
 * Parse a `.plan` (QGC JSON) file into waypoints plus any fence / rally it
 * carries. Survey / corridor / structure grids (ComplexItem) are expanded into
 * waypoints; an unexpandable complex item throws rather than dropping silently.
 */
export function parseQGCPlan(text: string): ParsedPlan {
  const data = JSON.parse(text) as QGCPlanFile;
  if (data.fileType !== "Plan" || !data.mission?.items) {
    throw new Error("Invalid .plan file — missing Plan fileType or mission items");
  }

  const flat: Waypoint[] = [];
  for (const item of data.mission.items) {
    expandPlanItem(item, flat);
  }

  return {
    // Fold DO / CONDITION sibling items into their navigation waypoint's actions.
    waypoints: foldLegacyWaypoints(flat),
    geofence: parseQGCGeoFence(data.geoFence),
    rally: parseQGCRally(data.rallyPoints),
  };
}
