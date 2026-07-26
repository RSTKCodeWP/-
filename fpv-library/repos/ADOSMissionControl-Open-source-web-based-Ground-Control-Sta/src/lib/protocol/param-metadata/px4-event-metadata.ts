/**
 * PX4 events component-metadata (component-metadata type 2).
 *
 * The FC advertises an events metadata file alongside the parameter metadata,
 * in the same general-metadata file. It maps each event id to a human-readable
 * message template + argument definitions, so a decoded EVENT (msg 410) frame
 * can be rendered as text. Best-effort throughout: any failure resolves to an
 * empty map so the caller degrades gracefully. Never throws.
 *
 * The full event id in the EVENT message is `(componentId << 24) | subId`,
 * where the metadata keys components by id string and events by sub-id string.
 *
 * @module protocol/param-metadata/px4-event-metadata
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "../types/protocol";
import {
  waitForComponentMetadataUri,
  fetchJsonFile,
  type GeneralMetadataFile,
} from "./px4-live-overlay";

/** COMP_METADATA_TYPE_EVENTS per the MAVLink component-metadata protocol enum. */
const COMP_METADATA_TYPE_EVENTS = 2;

/** One enum defined in an events metadata component. */
export interface EventEnumMeta {
  type: string;
  isBitfield?: boolean;
  entries: Record<string, { name: string; description?: string }>;
}

/** One argument of an event message template. */
export interface EventArgMeta {
  /** Base type string, e.g. "uint8_t", "float", or an enum name. */
  type: string;
  name?: string;
}

/** Resolved metadata for one event id. */
export interface EventMeta {
  name: string;
  message: string;
  description?: string;
  args: EventArgMeta[];
  /** The event's component enums, shared for enum-argument resolution. */
  enums?: Record<string, EventEnumMeta>;
}

interface EventsMetadataFile {
  version?: number;
  components?: Record<
    string,
    {
      namespace?: string;
      enums?: Record<string, EventEnumMeta>;
      event_groups?: Record<
        string,
        {
          events?: Record<
            string,
            {
              name?: string;
              message?: string;
              description?: string;
              arguments?: Array<{ type?: string; name?: string }>;
            }
          >;
        }
      >;
    }
  >;
}

const EMPTY: Map<number, EventMeta> = new Map();

/** Flatten a parsed events metadata file into `fullId -> EventMeta`. Exported
 * for unit testing; `fullId = (componentId << 24) | subId(24-bit)`. */
export function parseEventsMetadata(file: EventsMetadataFile): Map<number, EventMeta> {
  const out = new Map<number, EventMeta>();
  for (const [compKey, comp] of Object.entries(file.components ?? {})) {
    const compId = Number(compKey);
    if (!Number.isFinite(compId)) continue;
    const enums = comp.enums;
    for (const group of Object.values(comp.event_groups ?? {})) {
      for (const [subKey, ev] of Object.entries(group.events ?? {})) {
        const subId = Number(subKey);
        if (!Number.isFinite(subId) || !ev.name) continue;
        const fullId = (((compId & 0xff) << 24) | (subId & 0xffffff)) >>> 0;
        out.set(fullId, {
          name: ev.name,
          message: ev.message ?? ev.name,
          description: ev.description,
          args: (ev.arguments ?? []).map((a) => ({ type: a.type ?? "uint32_t", name: a.name })),
          enums,
        });
      }
    }
  }
  return out;
}

/**
 * Best-effort fetch of the PX4 FC-served events metadata. Always resolves; any
 * failure returns an empty map. Never throws. Shares the single COMPONENT_METADATA
 * round-trip with the parameter overlay (same general-metadata file).
 */
export async function fetchPx4LiveEventMetadata(
  protocol: DroneProtocol,
): Promise<Map<number, EventMeta>> {
  try {
    const generalUri = await waitForComponentMetadataUri(protocol);
    if (!generalUri) return EMPTY;

    const general = await fetchJsonFile<GeneralMetadataFile>(protocol, generalUri);
    if (!general || !Array.isArray(general.metadataTypes)) return EMPTY;

    const entry = general.metadataTypes.find((m) => m.type === COMP_METADATA_TYPE_EVENTS);
    if (!entry?.uri) return EMPTY;

    const file = await fetchJsonFile<EventsMetadataFile>(protocol, entry.uri);
    if (!file?.components) return EMPTY;

    return parseEventsMetadata(file);
  } catch (err) {
    console.warn("[event-metadata] PX4 live events overlay fetch failed", err);
    return EMPTY;
  }
}

// ── Argument substitution ──────────────────────────────────────────────────

/** Byte size of each MAVLink argument base type. */
const ARG_SIZES: Record<string, number> = {
  uint8_t: 1, int8_t: 1, uint16_t: 2, int16_t: 2,
  uint32_t: 4, int32_t: 4, float: 4, uint64_t: 8, int64_t: 8,
};

/** Read one argument value from the packed byte array (little-endian). Returns
 * the numeric value and the consumed size; unknown types consume 0 bytes. */
function readArg(dv: DataView, offset: number, type: string): { value: number; size: number } {
  switch (type) {
    case "uint8_t": return { value: dv.getUint8(offset), size: 1 };
    case "int8_t": return { value: dv.getInt8(offset), size: 1 };
    case "uint16_t": return { value: dv.getUint16(offset, true), size: 2 };
    case "int16_t": return { value: dv.getInt16(offset, true), size: 2 };
    case "uint32_t": return { value: dv.getUint32(offset, true), size: 4 };
    case "int32_t": return { value: dv.getInt32(offset, true), size: 4 };
    case "float": return { value: dv.getFloat32(offset, true), size: 4 };
    case "uint64_t": return { value: Number(dv.getBigUint64(offset, true)), size: 8 };
    case "int64_t": return { value: Number(dv.getBigInt64(offset, true)), size: 8 };
    default: return { value: 0, size: 0 };
  }
}

/** Format one placeholder `{idx[:.N][unit]}` against a resolved argument. */
function formatValue(
  value: number,
  arg: EventArgMeta | undefined,
  spec: string | undefined,
  enums?: Record<string, EventEnumMeta>,
): string {
  // Enum resolution: if the arg's type names an enum, show the entry name.
  if (arg && enums && enums[arg.type] && !enums[arg.type].isBitfield) {
    const entry = enums[arg.type].entries[String(value)];
    if (entry) return entry.name;
  }
  if (!spec) return String(value);
  // spec = optional ".N" decimal digits, then an optional unit suffix.
  const m = spec.match(/^\.(\d+)(.*)$/);
  if (m) {
    const digits = Number(m[1]);
    const unit = m[2] ?? "";
    return value.toFixed(digits) + unit;
  }
  // No decimals — the whole spec is a unit suffix.
  return String(value) + spec;
}

/**
 * Render an event message template by substituting its `{idx[:spec]}`
 * placeholders (1-based) with values read from the packed argument bytes,
 * decoded per the argument type definitions. Placeholders whose arguments are
 * absent are left as-is. Pure + total — never throws.
 */
export function renderEventMessage(
  template: string,
  argBytes: Uint8Array,
  argDefs: EventArgMeta[],
  enums?: Record<string, EventEnumMeta>,
): string {
  if (argDefs.length === 0) return template;
  const dv = new DataView(argBytes.buffer, argBytes.byteOffset, argBytes.byteLength);
  // Read every argument once at its running offset. Enum-typed args carry the
  // enum name as their `type`; the wire value is read using the enum's own
  // underlying base type.
  const values: number[] = [];
  let offset = 0;
  for (const arg of argDefs) {
    const wireType = enums && enums[arg.type] ? enums[arg.type].type : arg.type;
    const size = ARG_SIZES[wireType] ?? 0;
    if (size === 0 || offset + size > argBytes.byteLength) {
      values.push(NaN);
      continue;
    }
    const { value } = readArg(dv, offset, wireType);
    values.push(value);
    offset += size;
  }
  return template.replace(/\{(\d+)(?::([^}]*))?\}/g, (whole, idxStr: string, spec?: string) => {
    const idx = Number(idxStr) - 1; // 1-based in templates
    if (idx < 0 || idx >= values.length || Number.isNaN(values[idx])) return whole;
    return formatValue(values[idx], argDefs[idx], spec, enums);
  });
}
