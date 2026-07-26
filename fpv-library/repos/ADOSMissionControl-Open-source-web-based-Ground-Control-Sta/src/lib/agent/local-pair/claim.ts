/**
 * @module agent/local-pair/claim
 * @description The credential-claim half of the pair flow. POSTs the
 * agent's ``/api/pairing/claim`` route with the browser-local UUID as
 * the owner id and returns the durable API key the GCS uses for every
 * subsequent call.
 * @license GPL-3.0-only
 */

import { getBrowserId } from "@/stores/browser-identity-store";
import type { ClaimResult } from "./types";
import { AgentAlreadyPairedError, PairClientError } from "./errors";
import { combineSignals, normaliseHost, shouldUseProxy } from "./transport";

/** POST ``/api/pairing/claim`` with the browser-local UUID as ``user_id``.
 * The browser UUID acts as the pair owner id — the agent treats it
 * as the credential for unpair on subsequent requests.
 */
export async function pairLocally(
  rawHost: string,
  signal?: AbortSignal,
): Promise<ClaimResult> {
  const host = normaliseHost(rawHost);
  const userId = getBrowserId();
  const resp = shouldUseProxy()
    ? await fetch(`/api/lan-pair/claim`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ host, userId }),
        signal: combineSignals(signal),
      })
    : await fetch(`${host}/api/pairing/claim`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ user_id: userId }),
        signal: combineSignals(signal),
      });
  if (resp.status === 409) {
    throw new AgentAlreadyPairedError();
  }
  if (!resp.ok) {
    throw new PairClientError(
      "pairFailedStatusError",
      `Pair failed: ${resp.status} ${resp.statusText}`,
      { status: resp.status, statusText: resp.statusText },
    );
  }
  const body = (await resp.json()) as Record<string, unknown>;
  return {
    apiKey: String(body.api_key ?? ""),
    deviceId: String(body.device_id ?? ""),
    name: String(body.name ?? "ADOS Agent"),
    mdnsHost: String(body.mdns_host ?? ""),
    hostname: host,
  };
}
