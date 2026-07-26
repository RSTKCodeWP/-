/**
 * @module LanPairPinStatusRoute
 * @description Server-side proxy for the LAN agent's
 * `/api/dashboard/pin/status` endpoint (the dashboard-access PIN posture).
 *
 * The browser POSTs `{ host, apiKey }`. The server GETs the agent's public
 * status route, forwarding the API key in `X-ADOS-Key` (harmless — the status
 * route is public, but the uniform shape keeps the proxy simple). Body + status
 * are returned verbatim. The key stays under browser control; it just relays
 * through the server in one request.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 8000;

export async function POST(req: NextRequest) {
  let payload: { host?: string; apiKey?: string };
  try {
    payload = (await req.json()) as { host?: string; apiKey?: string };
  } catch {
    return NextResponse.json(
      { error: "bad_json", message: "Request body must be JSON" },
      { status: 400 },
    );
  }

  const target = normaliseAndCheckHost(payload?.host ?? "");
  if ("error" in target) {
    return NextResponse.json({ error: target.error, message: target.message }, { status: 400 });
  }

  const apiKey = String(payload?.apiKey ?? "").trim();

  try {
    const base = await ipv4FetchBase(target);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (apiKey) headers["X-ADOS-Key"] = apiKey;
    const upstream = await fetch(`${base}/api/dashboard/pin/status`, {
      headers,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "upstream_unreachable", message: e instanceof Error ? e.message : String(e) },
      { status: 502 },
    );
  }
}
