/**
 * Connection module - type definitions
 *
 * Establishes the vocabulary for the multi-vehicle connection foundation.
 * Pure type-level setup; no runtime code.
 *
 * Architectural model (Mission Planner-style two-level):
 *   - Transports are the physical/logical comms channels (serial, TCP, UDP).
 *   - Vehicles are MAVLink endpoints identified by (sysid, compid).
 *   - One transport can carry N vehicles (e.g., a radio link serving multiple
 *     drones, a MAVProxy out, or an orchestration server forwarding a fleet).
 *
 * The ConnectionRegistry owns these entries; ipc-handlers.ts integrates it via
 * compatibility shims while single-vehicle reads stay untouched.
 */

import type { Transport } from '@ardudeck/comms';
import type { MAVLinkParser } from '@ardudeck/mavlink-ts';
import type { ConnectOptions } from '../../shared/ipc-channels.js';

/**
 * Globally unique transport identifier.
 *
 * Generated as a UUID when a transport is added to the registry. Stable for
 * the transport's lifetime; reused across IPC channels and the renderer-side
 * vehicle selector.
 */
export type TransportId = string;

/**
 * Globally unique vehicle key.
 *
 * Format: `${transportId}:${sysid}.${compid}`. Uniquely identifies a vehicle
 * across all transports in the registry, even when multiple transports happen
 * to carry vehicles with overlapping sysids (e.g., two SITL instances both
 * defaulting to sysid 1).
 */
export type VehicleKey = string;

/**
 * Build a `VehicleKey` from its components.
 *
 * Centralized so the format is defined exactly once. Stores, IPC events, and
 * the vehicle selector all derive keys through this helper rather than
 * concatenating strings inline.
 */
export const makeVehicleKey = (
  transportId: TransportId,
  sysid: number,
  compid: number,
): VehicleKey => `${transportId}:${sysid}.${compid}`;

/**
 * Configuration used to create a transport.
 *
 * Aliased to the existing `ConnectOptions` shape so the registry can accept the
 * same payloads the legacy `COMMS_CONNECT` channel already produces. Kept as a
 * distinct alias so the connection module can evolve its config independently
 * of the IPC contract later.
 */
export type TransportConfig = ConnectOptions;

/**
 * Per-transport runtime statistics surfaced to the renderer.
 *
 * Updated by the message-routing layer; read by the connection panel to render
 * per-transport health, and by diagnostics for bug reports.
 */
export interface TransportStats {
  packetsRx: number;
  packetsTx: number;
  /** Wall-clock timestamp (ms) of the most recent successful packet parse, or `null` if none yet. */
  lastPacketAt: number | null;
  /** Most recent transport-level error, if any. Cleared on reconnect. */
  lastError: string | null;
}

/**
 * Per-vehicle metadata held by the registry.
 *
 * The registry holds connection-layer truth (identity, mavType, board info,
 * heartbeat liveness). Telemetry, parameters, mission state, etc. live in
 * renderer Zustand stores keyed by `VehicleKey` - they are intentionally not
 * duplicated here.
 */
export interface VehicleEntry {
  /** Globally unique key for this vehicle (see `makeVehicleKey`). */
  readonly key: VehicleKey;
  /** Owning transport's ID - back-pointer to the parent `TransportEntry`. */
  readonly transportId: TransportId;
  /** MAVLink system ID from the heartbeat header. */
  readonly sysid: number;
  /** MAVLink component ID from the heartbeat header. */
  readonly compid: number;
  /** MAV_TYPE from the most recent heartbeat (0 until first heartbeat received). */
  mavType: number;
  /**
   * Board name resolved from AUTOPILOT_VERSION (e.g. "Pixhawk6C"), if known.
   * Matches the legacy `connectionState.boardId` semantics: the human-readable
   * board identifier, not the numeric `board_version` field.
   */
  boardId: string | null;
  /** Board UID from AUTOPILOT_VERSION, if known. Used for persistent per-board caches. */
  boardUid: string | null;
  /** Wall-clock timestamp (ms) of the most recent heartbeat from this vehicle. */
  lastHeartbeatAt: number;
}

/**
 * Per-transport entry held by the registry.
 *
 * Each transport owns its own `MAVLinkParser` instance and a map of vehicles
 * discovered on that transport. The registry guarantees that the parser and
 * vehicles map are mutually consistent - vehicles are only added/removed
 * through the registry's lifecycle methods.
 */
export interface TransportEntry {
  /** Globally unique transport ID (UUID). */
  readonly id: TransportId;
  /** Underlying transport instance (serial / tcp / udp). */
  readonly transport: Transport;
  /** Per-transport MAVLink parser. Each transport gets its own to keep frame state isolated. */
  readonly parser: MAVLinkParser;
  /** Original config used to create this transport. Useful for reconnect and UI display. */
  readonly config: TransportConfig;
  /** Mutable runtime statistics. */
  stats: TransportStats;
  /** Vehicles discovered on this transport, keyed by `VehicleKey`. */
  vehicles: Map<VehicleKey, VehicleEntry>;
}

/**
 * Snapshot of the registry's currently-active selection.
 *
 * Returned by `ConnectionRegistry.getActive()` for callers that want both the
 * active transport and the active vehicle in a single read. May be `null` if
 * nothing is currently selected (e.g., between disconnect and the next connect).
 */
export interface ActiveSelection {
  transport: TransportEntry;
  vehicle: VehicleEntry;
}
