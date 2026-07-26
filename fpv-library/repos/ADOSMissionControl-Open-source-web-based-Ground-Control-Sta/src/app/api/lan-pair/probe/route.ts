/**
 * @module LanPairProbeRoute
 * @description Server-side proxy for the LAN agent's
 * `/api/pairing/info` endpoint. Lets the browser probe a LAN agent
 * from an HTTPS Mission Control deployment without tripping the
 * browser's mixed-content guard — the cross-protocol step happens
 * server-side from Mission Control's Next.js layer instead of the
 * browser.
 *
 * Only forwards requests to private / mDNS / loopback hosts (SSRF
 * whitelist via `normaliseAndCheckHost`). Body and status are
 * forwarded verbatim so the downstream pair client can treat this
 * route as a drop-in replacement for the direct fetch.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase, resolveIpv4 } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 8000;

export async function POST(req: NextRequest) {
  let payload: { host?: string };
  try {
    payload = (await req.json()) as { host?: string };
  } catch {
    return NextResponse.json(
      { error: "bad_json", message: "Request body must be JSON" },
      { status: 400 },
    );
  }

  const target = normaliseAndCheckHost(payload?.host ?? "");
  if ("error" in target) {
    return NextResponse.json(
      { error: target.error, message: target.message },
      { status: 400 },
    );
  }

  try {
    // Talk to the agent over IPv4 so a .local host doesn't burn ~5 s on the
    // IPv6/AAAA lookup before falling back (see ../_ipv4). The 8 s timeout
    // stays as a backstop; with IPv4 the round-trip is sub-second.
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/pairing/info`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const text = await upstream.text();

    // Pass non-success responses through verbatim so error mapping
    // on the client stays consistent.
    if (!upstream.ok) {
      return new NextResponse(text, {
        status: upstream.status,
        headers: {
          "content-type":
            upstream.headers.get("content-type") ?? "application/json",
        },
      });
    }

    // Augment the agent's body with a server-resolved IPv4 hint so the GCS has
    // a fallback when the OS-level mDNS resolver in the browser stops returning
    // the .local hostname. This reuses the lookup ipv4FetchBase already did
    // above (an OS resolver cache hit), so it costs nothing.
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(text) as Record<string, unknown>;
    } catch {
      // Not JSON — pass through unchanged.
      return new NextResponse(text, {
        status: upstream.status,
        headers: {
          "content-type":
            upstream.headers.get("content-type") ?? "application/json",
        },
      });
    }

    const ipv4 = await resolveIpv4(target.host);
    if (ipv4 && !parsed.ipv4) {
      parsed.ipv4 = ipv4;
    }

    return NextResponse.json(parsed, { status: upstream.status });
  } catch (e) {
    return NextResponse.json(
      {
        error: "upstream_unreachable",
        message: e instanceof Error ? e.message : String(e),
      },
      { status: 502 },
    );
  }
}
