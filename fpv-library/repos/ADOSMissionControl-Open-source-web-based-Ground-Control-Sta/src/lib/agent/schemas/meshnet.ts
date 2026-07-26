/**
 * @module AgentSchemas/MeshNet
 * @description zod schemas for the MeshNet enrollment surface and the
 * network-peer list the agent ships when running in mesh-aware modes.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import { NumberLike } from "./primitives";

export const MeshNetEnrollmentSchema = z
  .object({
    enrolled: z.boolean(),
    droneId: z.string().optional(),
    fleetName: z.string().optional(),
    tier: NumberLike.optional(),
    enrolledSince: z.string().optional(),
  })
  .passthrough();

export const NetworkPeerSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    signal_dbm: NumberLike,
    last_seen: z.string(),
    battery_percent: NumberLike,
    distance_m: NumberLike,
    tier: NumberLike,
    link_type: z.string(),
  })
  .passthrough();

export const NetworkPeerListSchema = z.array(NetworkPeerSchema);
