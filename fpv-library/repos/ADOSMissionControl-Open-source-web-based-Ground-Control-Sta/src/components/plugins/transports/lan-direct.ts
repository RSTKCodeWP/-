/**
 * @module LanDirectTransport
 * @description Local-first install path. Posts the archive multipart to
 * the paired agent's `POST /api/plugins/install` endpoint over the LAN
 * with the `X-ADOS-Key` pairing key. Returns a job id the progress
 * toast can subscribe to over `ws://<agent>/api/plugins/jobs/<jobId>`.
 *
 * Failover triggers (callers decide whether to fall through to
 * cloud-relay):
 *   - `TypeError` from `fetch` (network unreachable, mixed-content,
 *     DNS failure)
 *   - `AbortError` when the 60s total ceiling fires
 *   - HTTP 5xx after the 10s connect window
 *
 * The dialog wraps the call in a try/catch and asks `shouldFailover()`
 * before kicking the cloud path, so the failover policy stays here in
 * one place.
 *
 * @license GPL-3.0-only
 */

import {
  LAN_CONNECT_TIMEOUT_MS,
  LAN_TOTAL_TIMEOUT_MS,
  type InstallKickoffResult,
  type TransportContext,
} from "./types";

export interface LanDirectInputs extends TransportContext {
  agentUrl: string;
  pairingKey: string;
  /** Random id minted by the dialog so the progress toast can subscribe
   * before the upload completes. The agent echoes it back on the
   * install response and on every WS frame. */
  jobId: string;
}

/** Custom error so callers can branch on failover-eligible failures. */
export class LanDirectError extends Error {
  readonly cause: LanDirectFailureCause;
  readonly status?: number;
  constructor(cause: LanDirectFailureCause, message: string, status?: number) {
    super(message);
    this.cause = cause;
    this.status = status;
  }
}

export type LanDirectFailureCause =
  | "network"
  | "timeout"
  | "server-5xx"
  | "server-4xx"
  | "auth-missing";

/**
 * Upload + install over LAN. Resolves with the kickoff result the
 * progress toast needs; throws `LanDirectError` on any wire-level
 * failure. The dialog inspects the `cause` field to decide whether
 * to fall over to cloud-relay.
 */
export async function installLanDirect(
  inputs: LanDirectInputs,
): Promise<InstallKickoffResult> {
  if (!inputs.pairingKey) {
    throw new LanDirectError(
      "auth-missing",
      "Drone is not paired. Pair the drone before installing a plugin.",
    );
  }

  const form = new FormData();
  form.append("file", inputs.file);
  form.append(
    "requested_permissions",
    JSON.stringify([...inputs.grantedPermissions]),
  );
  form.append("job_id", inputs.jobId);

  const controller = new AbortController();
  const totalTimer = setTimeout(
    () => controller.abort(new DOMException("total-timeout", "AbortError")),
    LAN_TOTAL_TIMEOUT_MS,
  );
  const connectTimer = setTimeout(
    () => controller.abort(new DOMException("connect-timeout", "AbortError")),
    LAN_CONNECT_TIMEOUT_MS,
  );

  let response: Response;
  try {
    response = await fetch(`${inputs.agentUrl}/api/plugins/install`, {
      method: "POST",
      headers: { "X-ADOS-Key": inputs.pairingKey },
      body: form,
      signal: controller.signal,
    });
    // First byte received. Cancel the connect timer; total still active.
    clearTimeout(connectTimer);
  } catch (err) {
    clearTimeout(connectTimer);
    clearTimeout(totalTimer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new LanDirectError(
        "timeout",
        "LAN upload timed out.",
      );
    }
    // `TypeError: Failed to fetch` is the browser's catch-all for
    // network unreachable, DNS failure, mixed-content block, and
    // connection refused. All of these are cloud-eligible.
    if (err instanceof TypeError) {
      throw new LanDirectError(
        "network",
        `LAN upload failed: ${err.message}`,
      );
    }
    throw new LanDirectError(
      "network",
      err instanceof Error ? err.message : String(err),
    );
  } finally {
    clearTimeout(connectTimer);
  }
  clearTimeout(totalTimer);

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    const cause: LanDirectFailureCause =
      response.status >= 500 ? "server-5xx" : "server-4xx";
    throw new LanDirectError(
      cause,
      buildAgentErrorMessage(response.status, text),
      response.status,
    );
  }

  // The agent's success envelope is the existing install response.
  // We don't read the body for anything other than confirmation; the
  // progress toast subscribes over WebSocket with the job id we minted.
  return {
    transport: "lan",
    jobId: inputs.jobId,
    pluginId: inputs.manifest.pluginId,
    pluginName: inputs.manifest.name,
    deviceId: inputs.deviceId,
  };
}

/** Policy: which `LanDirectError` causes should fall over to cloud? All
 * except hard 4xx (which usually means a bad archive or rejected
 * permission set — cloud won't fix that). */
export function shouldFailover(err: LanDirectError): boolean {
  return err.cause !== "server-4xx" && err.cause !== "auth-missing";
}

/**
 * Build a clear error message from the agent's response body. The
 * supervisor returns a structured envelope `{ok: false, kind, detail}`
 * on every non-2xx; surface `kind` and `detail` when present so the
 * operator sees something readable instead of a raw JSON blob. Falls
 * back to the original `<status>: <text>` shape when the body isn't
 * the structured envelope.
 */
export function buildAgentErrorMessage(status: number, text: string): string {
  if (text) {
    try {
      const parsed = JSON.parse(text) as unknown;
      if (
        parsed &&
        typeof parsed === "object" &&
        "kind" in parsed &&
        "detail" in parsed
      ) {
        const kind = String((parsed as { kind: unknown }).kind ?? "");
        const detail = String((parsed as { detail: unknown }).detail ?? "");
        if (kind || detail) {
          return `Agent rejected install (${kind || "error"}): ${
            detail || `HTTP ${status}`
          }`;
        }
      }
    } catch {
      // Body wasn't JSON — fall through to raw-text shape.
    }
  }
  return `Agent returned ${status}${text ? `: ${text}` : ""}`;
}
