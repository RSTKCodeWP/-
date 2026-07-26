/**
 * @module vision/resolve-vision-client
 * @description Resolve the vision model client for a surface. In demo mode it
 * returns the canned in-memory client so the Vision tab + model picker render
 * and exercise their flow with no agent; otherwise it builds the real
 * LAN-direct {@link VisionAgentClient} from the active agent connection, or
 * null when no LAN URL is known (cloud-only session).
 *
 * @license GPL-3.0-only
 */

import { isDemoMode } from "@/lib/utils";
import {
  visionClientFromAgent,
  type VisionClient,
} from "@/lib/agent/vision-client";
import { demoVisionClient } from "@/mock/mock-vision-client";

/** Resolve the vision client for the current session. Returns the demo client
 * under demo mode, the real LAN client when an agent URL is known, or null
 * (no LAN seam) otherwise. */
export function resolveVisionClient(
  agentUrl: string | null,
  apiKey: string | null,
): VisionClient | null {
  if (isDemoMode()) return demoVisionClient();
  return visionClientFromAgent(agentUrl, apiKey);
}
