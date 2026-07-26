/**
 * @module agent/agent-client/camera
 * @description Camera-roster methods for the agent REST client: the reconciled
 * roster read (`GET /api/video/roster`) and the operator write
 * (`PUT /api/video/roster`). Distinct from the legacy `extras.listCameras`
 * (`/api/video/cameras`, encoder role assignments) — this is the management
 * roster the Cameras surface renders + edits. Each takes a `RequestContext` so
 * the `AgentClient` class re-exposes them as instance methods.
 * @license GPL-3.0-only
 */

import type { CameraLegInput, RosterCamera } from "../feature-types";
import { coerceRoster } from "../camera-roster";
import { agentRequest, type RequestContext } from "./transport";

/** The reconciled camera roster (declared legs + discovered devices + live
 * state). Degrades to an empty list when the agent has no video pipeline. */
export async function getCameraRoster(
  ctx: RequestContext,
): Promise<RosterCamera[]> {
  const body = await agentRequest<{ cameras?: unknown }>(
    ctx,
    "/api/video/roster",
  );
  return coerceRoster(body?.cameras);
}

/** Persist the operator's declared leg list. The agent validates the list,
 * merges it by owner (preserving plugin-declared legs), and restarts the video
 * pipeline (~3 s), so callers show a restart indicator + re-read after. Throws
 * with the agent's message on a validation (400) / unreachable (503) failure. */
export async function setCameraRoster(
  ctx: RequestContext,
  cameras: CameraLegInput[],
): Promise<void> {
  await agentRequest<unknown>(ctx, "/api/video/roster", {
    method: "PUT",
    body: JSON.stringify({ cameras }),
    // The write dials the supervisor + restarts the pipeline; give it more
    // headroom than a plain read.
    timeoutMs: 15000,
  });
}
