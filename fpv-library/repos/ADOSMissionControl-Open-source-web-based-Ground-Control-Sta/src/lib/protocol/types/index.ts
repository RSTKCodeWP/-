/**
 * Protocol abstraction layer types for Altnautica Command GCS.
 *
 * Defines a firmware-agnostic interface (`DroneProtocol`) so the GCS
 * can talk to ArduPilot, PX4, and (future) Betaflight/iNav through
 * a single API surface. Telemetry callback shapes are intentionally
 * compatible with the store types in `../../types.ts`.
 *
 * @module protocol/types
 */

export * from './transport';
export * from './enums';
export * from './core';
export * from './callbacks';
export * from './mission';
export * from './firmware';
export * from './protocol';
