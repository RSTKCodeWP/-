/**
 * Mission and log-related protocol types.
 *
 * @module protocol/types/mission
 */

/** On-board log entry received from LOG_ENTRY (msg 118). */
export interface LogEntry {
  id: number;
  numLogs: number;
  lastLogId: number;
  size: number;
  /** Seconds since 1970 UTC, or 0 if unavailable. */
  timeUtc: number;
}

/** Progress callback for log data download. */
export type LogDownloadProgressCallback = (receivedBytes: number, totalBytes: number) => void;

/** Progress callback for FTP file download. totalBytes is 0 when the size is unknown. */
export type FtpDownloadProgressCallback = (receivedBytes: number, totalBytes: number) => void;

/** Fence zone role: inclusion = stay inside, exclusion = stay outside. */
export type FenceRole = "inclusion" | "exclusion";

/**
 * Firmware-agnostic geofence element the GCS edits.
 *
 * PX4 stores the geofence as a mission plan (mission_type = fence), so a
 * polygon or circle maps to a NAV_FENCE_* mission item. ArduPilot uses the
 * legacy FENCE_POINT protocol and only its inclusion-polygon vertices.
 */
export type FenceElement =
  | {
      kind: "polygon";
      role: FenceRole;
      vertices: Array<{ lat: number; lon: number }>;
      /** Inclusion group (inclusion polygons only); ignored for exclusion. */
      group?: number;
    }
  | {
      kind: "circle";
      role: FenceRole;
      center: { lat: number; lon: number };
      /** Radius in meters. */
      radius: number;
      /** Inclusion group (inclusion circles only); ignored for exclusion. */
      group?: number;
    };

/** Wire-format mission item for upload/download (INT variant). */
export interface MissionItem {
  seq: number;
  /** MAV_FRAME enum. */
  frame: number;
  /** MAV_CMD enum. */
  command: number;
  current: number;
  autocontinue: number;
  param1: number;
  param2: number;
  param3: number;
  param4: number;
  /** Latitude * 1e7. */
  x: number;
  /** Longitude * 1e7. */
  y: number;
  /** Altitude in meters. */
  z: number;
}
