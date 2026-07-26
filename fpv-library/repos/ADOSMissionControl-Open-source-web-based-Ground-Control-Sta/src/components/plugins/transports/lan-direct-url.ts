/**
 * @module LanDirectUrlTransport
 * @description Local-first install path for registry plugins. Posts the
 * canonical archive URL (typically a published GitHub release asset)
 * along with its SHA-256 pin to the paired agent's
 * `POST /api/plugins/install_from_url` endpoint. The agent fetches the
 * archive itself, verifies the hash, runs the same supervisor flow as
 * the multipart install, and applies the requested permissions.
 *
 * This transport sidesteps the Convex storage upload entirely, so the
 * registry-card install path no longer requires an authenticated
 * Convex session. A drone paired on the LAN can install any registry
 * plugin without the operator being signed in to the cloud.
 *
 * Failover discipline mirrors {@link installLanDirect} so the dialog
 * can branch on the same `LanDirectError.cause` field for both
 * transports.
 *
 * @license GPL-3.0-only
 */

import {
  LanDirectError,
  buildAgentErrorMessage,
  type LanDirectFailureCause,
} from "./lan-direct";
import {
  LAN_CONNECT_TIMEOUT_MS,
  LAN_TOTAL_TIMEOUT_MS,
  type InstallKickoffResult,
} from "./types";

export interface LanDirectFromUrlInputs {
  /** Resolved LAN base URL for the target agent (no trailing slash). */
  agentUrl: string;
  /** Pairing key stamped into the `X-ADOS-Key` header. */
  pairingKey: string;
  /** Canonical archive URL the agent will fetch. */
  url: string;
  /** Lowercase hex SHA-256 of the archive bytes; the agent rejects on
   * mismatch with `sha256_mismatch`. */
  expectedSha256: string;
  /** Operator-approved permission ids. The agent grants each one
   * immediately after install, skipping the separate `/grant` call. */
  grantedPermissions: ReadonlyArray<string>;
  /** Random job id minted by the dialog so the progress toast can
   * subscribe over `ws://<agent>/api/plugins/jobs/<jobId>` before the
   * download completes. The agent writes sidecar progress under this
   * id and echoes it back on the response. */
  jobId: string;
  /** Manifest plugin id, surfaced on the kickoff result so the toast
   * can render a name before the agent finishes installing. */
  pluginId: string;
  /** Display name shown on the progress toast. */
  pluginName: string;
  /** Device id used by the progress toast to scope status queries. */
  deviceId: string;
  /** Set when the URL came from the first-party catalog browser. The
   * agent rejects ``from_catalog=true`` calls that ship without a
   * pinned ``expected_sha256``, so we forward the flag verbatim. */
  fromCatalog?: boolean;
}

/**
 * Drive the agent through the install-from-URL endpoint. Resolves with
 * the kickoff result the progress toast needs; throws `LanDirectError`
 * on any wire-level failure so the dialog can branch on the cause and
 * decide whether to fall over to cloud-relay.
 */
export async function installLanDirectFromUrl(
  inputs: LanDirectFromUrlInputs,
): Promise<InstallKickoffResult> {
  if (!inputs.pairingKey) {
    throw new LanDirectError(
      "auth-missing",
      "Drone is not paired. Pair the drone before installing a plugin.",
    );
  }

  const body = JSON.stringify({
    url: inputs.url,
    expected_sha256: inputs.expectedSha256,
    requested_permissions: [...inputs.grantedPermissions],
    job_id: inputs.jobId,
    from_catalog: inputs.fromCatalog === true,
  });

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
    response = await fetch(`${inputs.agentUrl}/api/plugins/install_from_url`, {
      method: "POST",
      headers: {
        "X-ADOS-Key": inputs.pairingKey,
        "Content-Type": "application/json",
      },
      body,
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
        "LAN install-from-URL timed out.",
      );
    }
    // `TypeError: Failed to fetch` is the browser's catch-all for
    // network unreachable, DNS failure, mixed-content block, and
    // connection refused. All of these are cloud-eligible.
    if (err instanceof TypeError) {
      throw new LanDirectError(
        "network",
        `LAN install-from-URL failed: ${err.message}`,
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

  return {
    transport: "lan",
    jobId: inputs.jobId,
    pluginId: inputs.pluginId,
    pluginName: inputs.pluginName,
    deviceId: inputs.deviceId,
  };
}
