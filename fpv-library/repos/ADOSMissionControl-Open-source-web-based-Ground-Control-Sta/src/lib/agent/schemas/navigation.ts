/**
 * @module AgentSchemas/Navigation
 * @description zod schema for the camera + vision navigation capability
 * block. Mirrors the NavigationCapability TypeScript shape on the
 * feature-types side. Four required fields cover the always-present
 * contract; the rest are optional metrics older agents may not emit.
 * Passthrough lets a future agent ship additional fields without tripping
 * the schema.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import {
  NullableNumber,
  NullableString,
  NumberLike,
} from "./primitives";

export const NavigationCapabilitySchema = z
  .object({
    opticalFlowSupported: z.boolean(),
    vioSupported: z.boolean(),
    rangefinderTopology: z
      .union([z.enum(["companion", "fc", "both"]), z.null()])
      .nullable(),
    recommendedCameraId: NullableString,
    flowQuality: NumberLike.optional(),
    flowRateHz: NumberLike.optional(),
    flowDistanceM: NullableNumber.optional(),
    vioState: z.string().optional(),
    vioResetCounter: NumberLike.optional(),
    vioQuality: NumberLike.optional(),
    companionState: z.string().optional(),
  })
  .passthrough();
