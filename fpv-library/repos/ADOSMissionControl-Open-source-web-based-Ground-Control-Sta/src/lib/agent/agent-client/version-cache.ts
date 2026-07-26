/**
 * @module agent/agent-client/version-cache
 * @description Module-level cache for `/api/version` responses so
 * multiple components hitting `getVersion()` in the same render frame
 * coalesce into a single network call.
 * @license GPL-3.0-only
 */

import type { AgentVersionInfo } from "../types";
import { AgentVersionInfoSchema } from "../schemas";
import { agentRequest, type RequestContext } from "./transport";
import type { z } from "zod";

const CAPABILITY_TTL_MS = 5 * 60 * 1000;

interface CachedVersion {
  info: AgentVersionInfo | null;
  expiresAt: number;
}

const versionCache = new Map<string, CachedVersion>();

/**
 * Fetch the agent's wire-protocol version + capability flags.
 * Returns null when the agent is older than 0.8.6 (does not have
 * the endpoint). Cached for 5 minutes per baseUrl+apiKey to avoid
 * burning requests when multiple components ask in the same frame.
 */
export async function fetchVersionInfo(
  ctx: RequestContext,
  opts?: { force?: boolean },
): Promise<AgentVersionInfo | null> {
  const key = `${ctx.baseUrl}|${ctx.apiKey ?? ""}`;
  const cached = versionCache.get(key);
  if (cached && !opts?.force && Date.now() < cached.expiresAt) {
    return cached.info;
  }
  let info: AgentVersionInfo | null = null;
  try {
    info = await agentRequest<AgentVersionInfo>(ctx, "/api/version", {
      schema: AgentVersionInfoSchema as z.ZodType<AgentVersionInfo>,
    });
  } catch (err) {
    // Older agent (pre-0.8.6) has no /api/version. Treat as
    // "no capabilities advertised" so callers fall back to the
    // legacy code path. Other transport errors are also treated as
    // "no info"; the caller sees null and degrades.
    if (process.env.NODE_ENV !== "production") {
      console.debug("[agent-client] getVersion failed:", err);
    }
    info = null;
  }
  versionCache.set(key, {
    info,
    expiresAt: Date.now() + CAPABILITY_TTL_MS,
  });
  return info;
}

/**
 * Capability flag presence check that gracefully handles older agents
 * (where /api/version is absent). Falls back to feature absent.
 */
export function agentSupports(
  info: AgentVersionInfo | null | undefined,
  capability: string,
): boolean {
  if (!info) return false;
  return info.capabilities.includes(capability);
}
