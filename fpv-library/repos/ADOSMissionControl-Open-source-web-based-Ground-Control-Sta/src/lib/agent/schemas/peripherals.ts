/**
 * @module AgentSchemas/Peripherals
 * @description zod schemas for peripheral device summaries the agent
 * advertises (sensors, cameras, video, gimbal, compute add-ons).
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

import { NumberLike } from "./primitives";

export const PeripheralInfoSchema = z
  .object({
    name: z.string(),
    type: z.string(),
    category: z.enum([
      "sensor",
      "camera",
      "video",
      "gimbal",
      "compute",
    ]),
    bus: z.string(),
    address: z.string(),
    rate_hz: NumberLike,
    status: z.enum(["ok", "warning", "error", "offline"]),
    last_reading: z.string(),
  })
  .passthrough();

export const PeripheralListSchema = z.array(PeripheralInfoSchema);
