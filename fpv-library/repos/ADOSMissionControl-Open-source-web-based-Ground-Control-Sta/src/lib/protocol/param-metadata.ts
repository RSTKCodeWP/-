/**
 * Parameter metadata — public module surface.
 *
 * Firmware-dispatched, local-first provider for parameter definitions (enum
 * values, bitmask flags, ranges, units, defaults, advisory flags) across
 * ArduPilot, PX4, iNav, and Betaflight. Implementation lives in
 * `param-metadata/`; this barrel is the stable import path.
 *
 * @module protocol/param-metadata
 * @license GPL-3.0-only
 */

export type {
  ParamMetadata,
  ParamValueType,
  ArduPilotVehicle,
  SerializedMeta,
  ParamSnapshot,
  ParamSnapshotProvenance,
} from "./param-metadata/types";

export {
  loadParamMetadata,
  refreshParamMetadata,
  firmwareTypeToVehicle,
  type ParamMetadataQuery,
} from "./param-metadata/index";
