/**
 * @module AgentSchemas/Command
 * @description zod schema for the generic command-result envelope the agent
 * returns on POST endpoints.
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

export const CommandResultSchema = z
  .object({
    success: z.boolean(),
    message: z.string(),
    data: z.unknown().optional(),
  })
  .passthrough();
