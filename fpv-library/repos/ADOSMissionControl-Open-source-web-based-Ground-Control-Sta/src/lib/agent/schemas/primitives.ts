/**
 * @module AgentSchemas/Primitives
 * @description Shared zod helpers reused across every per-domain schema.
 * Not re-exported from the public barrel; callers import from the
 * domain-specific files (heartbeat, capabilities, etc.).
 *
 * @license GPL-3.0-only
 */

import { z } from "zod";

/**
 * Numeric coercion for fields that older agents shipped as strings.
 * Falls back to 0 on parse failure so the UI degrades gracefully.
 */
export const NumberLike = z.preprocess(
  (val) => {
    if (typeof val === "number") return val;
    if (typeof val === "string") {
      const n = Number(val);
      return Number.isFinite(n) ? n : 0;
    }
    return 0;
  },
  z.number(),
);

export const NullableNumber = z.union([z.number(), z.null()]).nullable();
export const NullableString = z.union([z.string(), z.null()]).nullable();
