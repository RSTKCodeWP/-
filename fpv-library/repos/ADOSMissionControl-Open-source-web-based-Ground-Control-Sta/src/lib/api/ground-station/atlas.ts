// Atlas keyframe relay status on a ground-station node.
//
// The GS bridges the drone's WFB aux lane (small Atlas events) onto the LAN,
// forwarding each decoded keyframe datagram to the compute node. This read
// surfaces the relay's received-side counters so the operator sees the field
// lane is delivering. The endpoint is absent (404) when no relay is active, so
// the read returns null rather than throwing.

import { gsRequest, type RequestContext } from "./request";

/** Counters + config for the GS-side Atlas keyframe relay. */
export interface AtlasRelayStatus {
  /** Whether a relay loop is currently running on this node. */
  up: boolean;
  /** Datagrams read off the decoded aux port (received-side liveness proof). */
  datagramsSeen: number;
  /** Events decoded and accepted by the compute receiver. */
  forwarded: number;
  /** Datagrams that did not decode to an Atlas event (dropped). */
  malformed: number;
  /** Events that decoded but the forward POST to the compute node failed. */
  forwardFailed: number;
  /** The compute node base URL the relay forwards to. */
  computeUrl: string;
  /** The loopback port `wfb_rx -p 2` decodes the aux stream onto. */
  listenPort: number;
  /** Epoch ms the snapshot was produced (drives the staleness badge). */
  generatedAtMs: number;
}

function num(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function coerce(raw: unknown): AtlasRelayStatus | null {
  if (!raw || typeof raw !== "object") return null;
  const e = raw as Record<string, unknown>;
  return {
    up: e.up === true,
    datagramsSeen: num(e.datagrams_seen),
    forwarded: num(e.forwarded),
    malformed: num(e.malformed),
    forwardFailed: num(e.forward_failed),
    computeUrl: str(e.compute_url),
    listenPort: num(e.listen_port),
    generatedAtMs: num(e.generated_at_ms),
  };
}

/**
 * Read the GS-side Atlas relay status. Returns null when the endpoint is absent
 * (no relay active → 404) or unreachable, so the indicator simply stays hidden.
 */
export async function getAtlasRelayStatus(
  ctx: RequestContext,
): Promise<AtlasRelayStatus | null> {
  try {
    const raw = await gsRequest<unknown>(
      ctx,
      "/api/v1/ground-station/wfb/atlas-relay/status",
    );
    return coerce(raw);
  } catch {
    return null;
  }
}
