/**
 * @module LanPairArtifactRoute
 * @description Server-side, binary-safe proxy for a compute node's
 * reconstruction ARTIFACTS (the `/artifacts/*` blobs on the engine's own
 * `:8092` listener — a `.ply` splat/point cloud, a `.rrd` Rerun recording).
 *
 * Sibling to the JSON `/api/lan-pair/compute` proxy, but streams the raw body
 * (never `.text()`, which would corrupt a binary blob) and forwards the
 * `Range` request so large recordings can be range-fetched. Exists because the
 * engine stamps its artifact URLs with a drifting mDNS `.local` host the browser
 * cannot resolve (and mixed-content on an HTTPS GCS); routing through this
 * same-origin proxy resolves the paired host to IPv4 server-side and hands the
 * viewers a plain, reachable URL (Rule 39 local-first).
 *
 * GET `?host=<pairedHost>&path=artifacts/<relpath>&key=<apiKey?>`.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { resolveIpv4 } from "../_ipv4";

export const runtime = "nodejs";

/** Generous budget: an artifact can be tens/hundreds of MB over the LAN. */
const UPSTREAM_TIMEOUT_MS = 120000;
/** The ados-compute engine's own artifact/job port. */
const COMPUTE_JOB_PORT = "8092";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  const target = normaliseAndCheckHost(q.get("host") ?? "");
  if ("error" in target) {
    return NextResponse.json(
      { error: target.error, message: target.message },
      { status: 400 },
    );
  }

  // Only artifact blobs are proxyable here — defence-in-depth over the engine's
  // own path-jail. Strip a leading slash, reject traversal.
  const path = String(q.get("path") ?? "").replace(/^\/+/, "");
  if (!path.startsWith("artifacts/") || path.includes("..")) {
    return NextResponse.json(
      { error: "bad_path", message: "path must be an artifacts/ blob" },
      { status: 400 },
    );
  }

  const apiKey = String(q.get("key") ?? "").trim();
  const range = req.headers.get("range");

  try {
    // Resolve to IPv4 first so a .local host doesn't stall on the AAAA lookup,
    // then force the engine port.
    const ipv4 = await resolveIpv4(target.host);
    const u = new URL(target.url);
    u.hostname = ipv4 ?? target.host;
    u.port = COMPUTE_JOB_PORT;

    const upstream = await fetch(`${u.origin}/${path}`, {
      method: "GET",
      headers: {
        ...(apiKey ? { "X-ADOS-Key": apiKey } : {}),
        ...(range ? { Range: range } : {}),
      },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });

    // Stream the body through verbatim (200 full or 206 partial), preserving the
    // headers the loaders need. Same-origin, so no CORS/mixed-content concern.
    const headers = new Headers();
    for (const h of [
      "content-type",
      "content-length",
      "content-range",
      "accept-ranges",
      "last-modified",
      "etag",
    ]) {
      const v = upstream.headers.get(h);
      if (v) headers.set(h, v);
    }
    if (!headers.has("content-type")) {
      headers.set("content-type", "application/octet-stream");
    }
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers,
    });
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
