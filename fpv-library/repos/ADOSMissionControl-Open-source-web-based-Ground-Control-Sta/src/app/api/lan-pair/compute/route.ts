/**
 * @module LanPairComputeRoute
 * @description Server-side proxy for a compute node's job API
 * (`/api/compute/*` on the engine's own `:8092` listener). Sibling to the
 * pairing / vision-detector proxy routes (Rule 39 local-first): lets an HTTPS
 * Mission Control reach a plain-HTTP LAN compute node without tripping the
 * browser's mixed-content guard, and resolves `*.local` server-side.
 *
 * The browser POSTs `{ host, apiKey, path, method, body }`. The server forces
 * the engine job port (`:8092`), resolves the host to IPv4 (dodging the AAAA
 * stall on a `.local` box with no IPv6), forwards the request with the
 * `X-ADOS-Key` header, and streams the status + body back verbatim so the
 * client coerces the engine's response with no extra translation.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { resolveIpv4 } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 12000;
/** The ados-compute engine's own job-API port. */
const COMPUTE_JOB_PORT = "8092";

export async function POST(req: NextRequest) {
  let payload: {
    host?: string;
    apiKey?: string;
    path?: string;
    method?: string;
    body?: unknown;
  };
  try {
    payload = (await req.json()) as {
      host?: string;
      apiKey?: string;
      path?: string;
      method?: string;
      body?: unknown;
    };
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

  // Sub-path under /api/compute/ — strip a leading slash and reject traversal.
  const path = String(payload?.path ?? "").replace(/^\/+/, "");
  if (!path || path.includes("..")) {
    return NextResponse.json(
      { error: "bad_path", message: "path is required and must not traverse" },
      { status: 400 },
    );
  }

  const method = String(payload?.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "POST") {
    return NextResponse.json(
      { error: "bad_method", message: "Only GET and POST are supported" },
      { status: 400 },
    );
  }

  const apiKey = String(payload?.apiKey ?? "").trim();

  try {
    // Force the engine job port (:8092) and resolve to IPv4 first so a .local
    // host doesn't burn ~5 s on the AAAA lookup before falling back (../_ipv4).
    const ipv4 = await resolveIpv4(target.host);
    const u = new URL(target.url);
    u.hostname = ipv4 ?? target.host;
    u.port = COMPUTE_JOB_PORT;
    const base = u.origin;

    const hasBody =
      method === "POST" &&
      payload?.body !== undefined &&
      payload?.body !== null;

    const upstream = await fetch(`${base}/api/compute/${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...(apiKey ? { "X-ADOS-Key": apiKey } : {}),
      },
      body: hasBody ? JSON.stringify(payload.body) : undefined,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
      },
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
