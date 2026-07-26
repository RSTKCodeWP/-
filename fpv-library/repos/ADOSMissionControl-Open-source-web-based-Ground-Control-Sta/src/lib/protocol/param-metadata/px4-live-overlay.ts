/**
 * PX4 live (FC-served) parameter metadata overlay.
 *
 * PX4 advertises its own parameter metadata over MAVLink's component
 * metadata protocol: COMPONENT_METADATA (msg 397) points at a small general
 * metadata file, which in turn lists the parameter metadata file's URI. Both
 * files travel over MAVLink FTP (`mftp://`) or plain HTTP(S), and either may
 * be xz- or gzip-compressed.
 *
 * This is the exact-for-this-vehicle tier: it wins over the hosted and
 * bundled tiers when present. Best-effort throughout, so any failure (no
 * COMPONENT_METADATA reply, an unreachable file, malformed JSON, a missing
 * PARAMETER entry) resolves to an empty Map so the caller falls back to the
 * next tier. Never throws.
 *
 * @module protocol/param-metadata/px4-live-overlay
 * @license GPL-3.0-only
 */

import { XzReadableStream } from "xz-decompress";
import { ungzip } from "pako";
import type { DroneProtocol } from "../types/protocol";
import type { ParamMetadata, ParamValueType } from "./types";

/** COMP_METADATA_TYPE_PARAMETER, per the MAVLink component-metadata protocol enum. */
const COMP_METADATA_TYPE_PARAMETER = 1;

/** How long to wait (polling) for COMPONENT_METADATA to arrive after connect. */
const URI_WAIT_TIMEOUT_MS = 3000;
const URI_POLL_INTERVAL_MS = 200;

const XZ_MAGIC = [0xfd, 0x37, 0x7a, 0x58, 0x5a, 0x00];
const GZIP_MAGIC = [0x1f, 0x8b];

const EMPTY_MAP: Map<string, ParamMetadata> = new Map();

export interface GeneralMetadataFile {
  version: number;
  metadataTypes: Array<{ type: number; uri: string; fileCrc?: number }>;
}

interface Px4ParamEntry {
  name?: string;
  type?: string;
  shortDesc?: string;
  longDesc?: string;
  units?: string;
  default?: number;
  decimalPlaces?: number;
  min?: number;
  max?: number;
  increment?: number;
  rebootRequired?: boolean;
  group?: string;
  category?: string;
  volatile?: boolean;
  readOnly?: boolean;
  values?: Array<{ value?: number; description?: string }>;
  bitmask?: Array<{ index?: number; description?: string }>;
}

interface ParameterMetadataFile {
  version: number;
  parameters: Px4ParamEntry[];
}

/** PX4's `parameter.schema.json` type strings, mapped to our storage type. */
const PX4_TYPE_MAP: Record<string, ParamValueType> = {
  Uint8: "uint8", Int8: "int8", Uint16: "uint16", Int16: "int16",
  Uint32: "uint32", Int32: "int32", Float: "float",
};

function hasMagic(bytes: Uint8Array, magic: number[]): boolean {
  if (bytes.length < magic.length) return false;
  for (let i = 0; i < magic.length; i++) if (bytes[i] !== magic[i]) return false;
  return true;
}

/**
 * Decompress a fetched metadata file if it is xz- or gzip-compressed
 * (detected by magic bytes, not by URI extension). Plain JSON passes through
 * unchanged. A decompression failure surfaces as a JSON.parse failure in the
 * caller, which already treats that as best-effort.
 */
async function decompressAuto(bytes: Uint8Array): Promise<Uint8Array> {
  if (hasMagic(bytes, XZ_MAGIC)) {
    // Re-wrap into a fresh ArrayBuffer-backed copy: `bytes` may be typed as
    // Uint8Array<ArrayBufferLike> (e.g. from an FTP download), which BlobPart
    // does not accept; only the concrete Uint8Array<ArrayBuffer> form does.
    const stream = new XzReadableStream(new Blob([new Uint8Array(bytes)]).stream());
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }
  if (hasMagic(bytes, GZIP_MAGIC)) {
    return ungzip(bytes);
  }
  return bytes;
}

/**
 * Resolve a `mftp://` or `https://`/`http://` component-metadata URI to raw
 * bytes. Returns null on any failure or unsupported scheme.
 */
async function fetchUriBytes(protocol: DroneProtocol, uri: string): Promise<Uint8Array | null> {
  if (uri.startsWith("mftp://")) {
    if (!protocol.downloadFileViaFtp) return null;
    // mftp://[comp=N:]<path> per the MAVLink FTP URL scheme. This client
    // always downloads from the already-connected autopilot component, so a
    // comp= target prefix (cross-component metadata, rare in practice) is
    // stripped rather than honored. That is an accepted best-effort
    // limitation, not a silent lie: a file that genuinely lives on another
    // component would simply come back as a normal FTP "file not found" NAK.
    let rest = uri.slice("mftp://".length);
    const compMatch = rest.match(/^comp=\d+:/);
    if (compMatch) rest = rest.slice(compMatch[0].length);
    const path = rest.startsWith("/") ? rest : `/${rest}`;
    try {
      return await protocol.downloadFileViaFtp(path);
    } catch {
      return null;
    }
  }
  if (uri.startsWith("https://") || uri.startsWith("http://")) {
    try {
      const res = await fetch(uri);
      if (!res.ok) return null;
      return new Uint8Array(await res.arrayBuffer());
    } catch {
      return null;
    }
  }
  // Unknown scheme (e.g. a future addition to the spec). Never guess.
  return null;
}

/** Fetch + decompress + JSON.parse a metadata file. Null on any failure.
 * Shared by the parameter and events component-metadata overlays. */
export async function fetchJsonFile<T>(protocol: DroneProtocol, uri: string): Promise<T | null> {
  const raw = await fetchUriBytes(protocol, uri);
  if (!raw) return null;
  try {
    const decompressed = await decompressAuto(raw);
    return JSON.parse(new TextDecoder().decode(decompressed)) as T;
  } catch (err) {
    console.warn(`[param-metadata] failed to parse FC-served metadata file at ${uri}`, err);
    return null;
  }
}

/** Wait (bounded, polling) for COMPONENT_METADATA to have arrived. Shared by
 * the parameter and events component-metadata overlays. */
export async function waitForComponentMetadataUri(protocol: DroneProtocol): Promise<string | null> {
  if (!protocol.getComponentMetadataUri) return null;
  const deadline = Date.now() + URI_WAIT_TIMEOUT_MS;
  for (;;) {
    const uri = protocol.getComponentMetadataUri();
    if (uri) return uri;
    if (Date.now() >= deadline) return null;
    await new Promise((r) => setTimeout(r, URI_POLL_INTERVAL_MS));
  }
}

function toValuesMap(values?: Array<{ value?: number; description?: string }>): Map<number, string> | undefined {
  if (!Array.isArray(values)) return undefined;
  const map = new Map<number, string>();
  for (const v of values) {
    if (v.value === undefined) continue;
    map.set(v.value, String(v.description ?? ""));
  }
  return map.size ? map : undefined;
}

function toBitmaskMap(bitmask?: Array<{ index?: number; description?: string }>): Map<number, string> | undefined {
  if (!Array.isArray(bitmask)) return undefined;
  const map = new Map<number, string>();
  for (const b of bitmask) {
    if (b.index === undefined) continue;
    map.set(b.index, String(b.description ?? ""));
  }
  return map.size ? map : undefined;
}

/** Map one PX4 `parameter.schema.json` entry to our cross-firmware shape. */
function toParamMetadata(p: Px4ParamEntry): [string, ParamMetadata] | null {
  if (!p.name) return null;
  const range = p.min !== undefined && p.max !== undefined ? { min: p.min, max: p.max } : undefined;
  const meta: ParamMetadata = {
    name: p.name,
    humanName: p.shortDesc ?? "",
    description: p.longDesc ?? p.shortDesc ?? "",
    range,
    units: p.units || undefined,
    values: toValuesMap(p.values),
    bitmask: toBitmaskMap(p.bitmask),
    increment: p.increment,
    defaultValue: p.default,
    rebootRequired: p.rebootRequired === true ? true : undefined,
    volatile: p.volatile === true ? true : undefined,
    readOnly: p.readOnly === true ? true : undefined,
    decimalPlaces: p.decimalPlaces,
    valueType: p.type ? PX4_TYPE_MAP[p.type] : undefined,
    category: p.category || undefined,
    group: p.group || undefined,
  };
  return [p.name, meta];
}

/**
 * Best-effort fetch of the PX4 FC-served parameter metadata overlay. Always
 * resolves; any failure along the way returns an empty Map so the caller
 * degrades to the bundled/hosted tiers. Never throws.
 */
export async function fetchPx4LiveParamMetadata(
  protocol: DroneProtocol,
): Promise<Map<string, ParamMetadata>> {
  try {
    const generalUri = await waitForComponentMetadataUri(protocol);
    if (!generalUri) return EMPTY_MAP;

    const general = await fetchJsonFile<GeneralMetadataFile>(protocol, generalUri);
    if (!general || !Array.isArray(general.metadataTypes)) return EMPTY_MAP;

    const paramEntry = general.metadataTypes.find((m) => m.type === COMP_METADATA_TYPE_PARAMETER);
    if (!paramEntry?.uri) return EMPTY_MAP;

    const paramFile = await fetchJsonFile<ParameterMetadataFile>(protocol, paramEntry.uri);
    if (!paramFile || !Array.isArray(paramFile.parameters)) return EMPTY_MAP;

    const map = new Map<string, ParamMetadata>();
    for (const p of paramFile.parameters) {
      const entry = toParamMetadata(p);
      if (entry) map.set(entry[0], entry[1]);
    }
    return map;
  } catch (err) {
    console.warn("[param-metadata] PX4 live overlay fetch failed", err);
    return EMPTY_MAP;
  }
}
