import type { MockFrame } from "../mock/mock-ws";
import type { ContactRecord, JsonMessage } from "../types/wire";

/* Phase 6 — the baked static demo mission (`ui/public/mission.json`, produced by
 * `hades-record-mission`). The demo site replays this through the SAME UI the live service
 * drives; no Electron, no Python backend at runtime.
 *
 * The on-disk shape mirrors the UI's mock data path (`MockWsConfig`): `{frames, json}` where
 * frames carry their REAL wire frame_id (the cross-channel join key — a re-counted local index
 * would misalign every overlay), plus a single looped still (`frame_jpeg_b64`, stored once),
 * a provenance block the demo banner reads, and the scripted link-lost / refined-promote
 * timeline. `parseMission` decodes it into the in-memory `{frames, json}` the existing
 * `MockWsServer` already replays — so the file-source is "fetch + feed the mock server",
 * not a new transport. */

interface RawFrame {
  frame_id: number;
  timestamp: number;
}

interface RawMission {
  version: number;
  frame_jpeg_b64: string;
  frames: RawFrame[];
  json: JsonMessage[];
  link_lost: { from_frame: number; to_frame: number };
  promote_refined: ContactRecord | null;
  mission_epoch_ms: number;
  provenance: { scene: string; pipeline: string; median_error_m: number; note: string };
}

export interface Provenance {
  scene: string;
  pipeline: string;
  median_error_m: number;
  note: string;
}

export interface BakedMission {
  frames: MockFrame[];
  json: JsonMessage[];
  linkLost: { fromFrame: number; toFrame: number };
  promoteRefined: ContactRecord | null;
  missionEpochMs: number;
  provenance: Provenance;
}

/** Decode a base64 string to JPEG bytes (browser `atob`, also present in jsdom/Node tests). */
function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Validate + decode a parsed `mission.json` into the in-memory mission the UI replays. Throws
 * loudly on a malformed artifact (a bad bake should fail visibly, not render a half-empty demo). */
export function parseMission(raw: RawMission): BakedMission {
  if (!raw || !Array.isArray(raw.frames) || !Array.isArray(raw.json)) {
    throw new Error("mission.json: missing frames/json");
  }
  // ONE decode of the looped still, shared across every frame (the file is small for it).
  const jpeg = b64ToBytes(raw.frame_jpeg_b64);
  const frames: MockFrame[] = raw.frames.map((f) => ({
    frame_id: f.frame_id, // the REAL pipeline seq — the cross-channel join key
    timestamp: f.timestamp,
    jpeg,
  }));
  return {
    frames,
    json: raw.json,
    linkLost: { fromFrame: raw.link_lost.from_frame, toFrame: raw.link_lost.to_frame },
    promoteRefined: raw.promote_refined,
    missionEpochMs: raw.mission_epoch_ms,
    provenance: raw.provenance,
  };
}

/** Fetch + parse the baked mission, resolved RELATIVE to the page base (`import.meta.env.BASE_URL`)
 * so it loads under a GitHub-Pages subpath, a root host, AND `file://` alike. Returns null if the
 * artifact is absent (the caller falls back to the synthetic `cannedMission`). */
export async function loadMission(): Promise<BakedMission | null> {
  const base = import.meta.env.BASE_URL ?? "/";
  try {
    const res = await fetch(`${base}mission.json`);
    if (!res.ok) return null;
    return parseMission(await res.json());
  } catch {
    return null;
  }
}
