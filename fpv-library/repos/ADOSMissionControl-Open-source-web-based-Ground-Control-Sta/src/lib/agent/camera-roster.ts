/**
 * @module agent/camera-roster
 * @description Pure helpers for the camera roster: defensive coercion of the
 * agent's `GET /api/video/roster` payload into {@link RosterCamera}[], and the
 * builders that turn a roster + one operator edit into the full declared leg
 * list the `PUT /api/video/roster` write sends.
 *
 * The write is a whole-list replace of the OPERATOR legs (the agent merges by
 * owner, preserving plugin-declared legs), so every mutation is expressed as
 * "the roster's operator legs, with this one change applied" — plugin-owned and
 * not-yet-assigned discovered rows are left out, an assigned/offline row is kept
 * and patched, and a discovered row being edited is promoted to a declared leg.
 * Pure + side-effect-free so the leg matrix is unit-tested.
 *
 * @license GPL-3.0-only
 */

import type {
  CameraFingerprint,
  CameraLegInput,
  RosterCamera,
  RosterCameraState,
} from "./feature-types";

/** Operator edit to one camera (a subset of the leg's editable fields). */
export interface CameraPatch {
  name?: string | null;
  orientation?: string | null;
  purpose?: string[];
  enabled?: boolean;
  /** `"primary"` designates the primary stream; `null` clears the role. */
  role?: string | null;
  fov_deg?: number | null;
  mount_pitch_deg?: number | null;
}

// ── coercion ──────────────────────────────────────────────────

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}
function strOrNull(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}
function numOrNull(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function boolOrNull(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}
function strArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((e): e is string => typeof e === "string") : [];
}

const STATES: ReadonlyArray<RosterCameraState> = [
  "assigned",
  "discovered_unassigned",
  "plugin_owned",
  "offline",
];

function coerceState(v: unknown): RosterCameraState {
  return typeof v === "string" && (STATES as readonly string[]).includes(v)
    ? (v as RosterCameraState)
    : "assigned";
}

function coerceMatch(v: unknown): CameraFingerprint | null {
  if (!v || typeof v !== "object") return null;
  const e = v as Record<string, unknown>;
  const m: CameraFingerprint = {};
  if (typeof e.usb === "string") m.usb = e.usb;
  if (typeof e.csi_sensor === "string") m.csi_sensor = e.csi_sensor;
  if (typeof e.csi_port === "number") m.csi_port = e.csi_port;
  return m.usb || m.csi_sensor || m.csi_port !== undefined ? m : null;
}

/** Coerce the raw `cameras` array of `GET /api/video/roster` into a stable
 * roster shape. A row with no `id` is dropped; unknown fields are ignored so a
 * newer agent round-trips without a GCS release. */
export function coerceRoster(raw: unknown): RosterCamera[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return [];
    const e = entry as Record<string, unknown>;
    const id = str(e.id);
    if (!id) return [];
    return [
      {
        id,
        name: strOrNull(e.name),
        source: str(e.source),
        role: strOrNull(e.role),
        purpose: strArray(e.purpose),
        orientation: strOrNull(e.orientation),
        enabled: e.enabled === true,
        owner: strOrNull(e.owner),
        state: coerceState(e.state),
        live: boolOrNull(e.live),
        device_path: strOrNull(e.device_path),
        width: numOrNull(e.width),
        height: numOrNull(e.height),
        fps: numOrNull(e.fps),
        codec: strOrNull(e.codec),
        bitrate_kbps: numOrNull(e.bitrate_kbps),
        calibration: strOrNull(e.calibration),
        match: coerceMatch(e.match),
        fov_deg: numOrNull(e.fov_deg),
        mount_pitch_deg: numOrNull(e.mount_pitch_deg),
      },
    ];
  });
}

// ── leg builders ──────────────────────────────────────────────

/** True for a row the operator declares (kept + patched on write). A
 * plugin-owned row is preserved server-side (merge-by-owner); a discovered
 * device is not declared until the operator assigns it. */
export function isOperatorDeclared(c: RosterCamera): boolean {
  return c.state !== "plugin_owned" && c.state !== "discovered_unassigned";
}

/** Build one leg from a roster row, applying an optional edit. Numeric /
 * codec fields ride only when the roster carries a real value (the agent's
 * leg schema has non-null defaults for those, so a `null` would be rejected). */
export function legFromCamera(
  cam: RosterCamera,
  patch?: CameraPatch,
): CameraLegInput {
  const p = patch ?? {};
  const leg: CameraLegInput = {
    id: cam.id,
    source: cam.source,
    purpose: p.purpose ?? cam.purpose,
    enabled: p.enabled ?? cam.enabled,
    role: p.role !== undefined ? p.role : (cam.role ?? null),
    orientation:
      p.orientation !== undefined ? p.orientation : (cam.orientation ?? null),
    name: p.name !== undefined ? p.name : (cam.name ?? null),
    fov_deg: p.fov_deg !== undefined ? p.fov_deg : (cam.fov_deg ?? null),
    mount_pitch_deg:
      p.mount_pitch_deg !== undefined
        ? p.mount_pitch_deg
        : (cam.mount_pitch_deg ?? null),
  };
  if (typeof cam.codec === "string" && cam.codec) leg.codec = cam.codec;
  if (typeof cam.width === "number") leg.width = cam.width;
  if (typeof cam.height === "number") leg.height = cam.height;
  if (typeof cam.fps === "number") leg.fps = cam.fps;
  // Round-trip the transmit bitrate + opaque calibration so a write never
  // resets them to the agent's compiled default (they ride only when the
  // roster carried a real value).
  if (typeof cam.bitrate_kbps === "number") leg.bitrate_kbps = cam.bitrate_kbps;
  if (typeof cam.calibration === "string") leg.calibration = cam.calibration;
  if (cam.match) leg.match = cam.match;
  return leg;
}

/** The declared operator legs of a roster (the base of every write). */
export function rosterToLegs(roster: RosterCamera[]): CameraLegInput[] {
  return roster.filter(isOperatorDeclared).map((c) => legFromCamera(c));
}

/** When one leg is designated primary, demote any other leg still holding the
 * `primary` role so exactly one primary survives. A demoted leg carrying the
 * reserved primary id `"main"` is re-slugged off it — the agent rejects a
 * non-primary `"main"`, so clearing the role alone would 400 the write. */
function demoteOtherPrimaries(
  legs: CameraLegInput[],
  primaryId: string,
): CameraLegInput[] {
  return legs.map((l) => {
    if (l.id === primaryId || l.role !== "primary") return l;
    const demoted: CameraLegInput = { ...l, role: null };
    if (demoted.id !== RESERVED_PRIMARY_ID) return demoted;
    const others = legs.filter((o) => o.id !== l.id).map((o) => o.id);
    return { ...demoted, id: slugCameraId(l.name ?? l.id, others) };
  });
}

/** The leg list to PUT after editing (or assigning) one camera. An assigned /
 * offline row is patched in place; a discovered row is promoted to a new
 * (enabled) declared leg. */
export function legsWithEdit(
  roster: RosterCamera[],
  id: string,
  patch: CameraPatch,
): CameraLegInput[] {
  const cam = roster.find((c) => c.id === id);
  const base = rosterToLegs(roster);
  let legs: CameraLegInput[];
  if (cam && isOperatorDeclared(cam)) {
    legs = base.map((l) => (l.id === id ? legFromCamera(cam, patch) : l));
  } else if (cam) {
    legs = [...base, legFromCamera(cam, { enabled: true, ...patch })];
  } else {
    legs = base;
  }
  return patch.role === "primary" ? demoteOtherPrimaries(legs, id) : legs;
}

/** The leg list to PUT after toggling one camera's enabled flag. */
export function legsWithToggle(
  roster: RosterCamera[],
  id: string,
  enabled: boolean,
): CameraLegInput[] {
  return legsWithEdit(roster, id, { enabled });
}

/** The leg list to PUT after removing one leg (dropped from the declared list;
 * a device it named reappears as a discovered candidate on the next read). */
export function legsWithRemove(
  roster: RosterCamera[],
  id: string,
): CameraLegInput[] {
  return rosterToLegs(roster).filter((l) => l.id !== id);
}

/** The leg list to PUT after appending a new (network) leg. */
export function legsWithAdd(
  roster: RosterCamera[],
  leg: CameraLegInput,
): CameraLegInput[] {
  return [...rosterToLegs(roster), leg];
}

/** The leg id the agent reserves for the primary stream (its mediamtx `main`
 * path). A non-primary leg carrying this id is rejected by the agent, so a
 * newly-slugged operator leg must never claim it. */
export const RESERVED_PRIMARY_ID = "main";

/** Slugify a display name into a path-safe, unique leg id (`Belly cam` →
 * `belly-cam`), disambiguating against `taken` — and against the reserved
 * primary id `"main"` — with a numeric suffix. A camera literally named
 * "Main" therefore slugs to `main-2`, never the bare reserved `"main"`. */
export function slugCameraId(name: string, taken: ReadonlyArray<string>): string {
  const base =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "ip-cam";
  const isFree = (id: string) => id !== RESERVED_PRIMARY_ID && !taken.includes(id);
  if (isFree(base)) return base;
  for (let i = 2; i < 1000; i += 1) {
    const candidate = `${base}-${i}`;
    if (isFree(candidate)) return candidate;
  }
  return `${base}-${Date.now()}`;
}
