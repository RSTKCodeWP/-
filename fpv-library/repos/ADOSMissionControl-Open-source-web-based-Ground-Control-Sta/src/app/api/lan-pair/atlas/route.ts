/**
 * @module LanPairAtlasRoute
 * @description Server-side proxy for a drone agent's Atlas capture-control
 * surface (`/api/atlas/*` on the ados-control front, `:8080`). Sibling to the
 * pairing / vision / compute proxy routes (Rule 39 local-first): lets an HTTPS
 * Mission Control reach a plain-HTTP LAN agent without tripping the browser's
 * mixed-content guard, and resolves `*.local` server-side.
 *
 * The browser POSTs `{ host, apiKey, path, method, body }`. Unlike the compute
 * proxy this keeps the host's own port (`:8080` — Atlas is on the control front,
 * not the engine's `:8092`) and permits PUT (for `PUT /api/atlas/config`). The
 * request is forwarded with the `X-ADOS-Key` header and the upstream status +
 * body are streamed back verbatim so the client coerces the agent's response
 * (and sees a real `503` from a down capture service) with no translation.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 12000;

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

  // Sub-path under /api/atlas/ — strip a leading slash and reject traversal.
  const path = String(payload?.path ?? "").replace(/^\/+/, "");
  if (!path || path.includes("..")) {
    return NextResponse.json(
      { error: "bad_path", message: "path is required and must not traverse" },
      { status: 400 },
    );
  }

  const method = String(payload?.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "POST" && method !== "PUT") {
    return NextResponse.json(
      { error: "bad_method", message: "Only GET, POST and PUT are supported" },
      { status: 400 },
    );
  }

  const apiKey = String(payload?.apiKey ?? "").trim();

  try {
    // Resolve to IPv4 first so a .local host doesn't stall ~5 s on the AAAA
    // lookup; ipv4FetchBase keeps the host's own :8080 port (../_ipv4).
    const base = await ipv4FetchBase(target);

    const hasBody =
      (method === "POST" || method === "PUT") &&
      payload?.body !== undefined &&
      payload?.body !== null;

    const upstream = await fetch(`${base}/api/atlas/${path}`, {
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
