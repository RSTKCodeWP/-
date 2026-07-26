/**
 * @module AgentSchemas/Pairing
 * @description zod schemas for pairing-related agent responses.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import { NumberLike } from "./primitives";

export const PairingInfoSchema = z
  .object({
    device_id: z.string(),
    name: z.string(),
    version: z.string(),
    board: z.string(),
    paired: z.boolean(),
    pairing_code: z.string().optional(),
    owner_id: z.string().optional(),
    paired_at: NumberLike.optional(),
    mdns_host: z.string(),
  })
  .passthrough();

export const ClaimResponseSchema = z
  .object({
    api_key: z.string(),
    device_id: z.string(),
    name: z.string(),
    mdns_host: z.string(),
  })
  .passthrough();
