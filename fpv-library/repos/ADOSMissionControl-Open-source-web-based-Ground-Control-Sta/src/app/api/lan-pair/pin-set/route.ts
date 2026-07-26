/**
 * @module LanPairPinSetRoute
 * @description Server-side proxy for the LAN agent's `/api/dashboard/pin/set`
 * endpoint (set/replace the dashboard-access PIN).
 *
 * The browser POSTs `{ host, apiKey, pin }`. The server forwards the API key in
 * `X-ADOS-Key` (which authorizes the change on the agent) and the `{ pin }` body.
 * Body + status are returned verbatim. The key stays under browser control; it
 * just relays through the server in one request.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 8000;

export async function POST(req: NextRequest) {
  let payload: { host?: string; apiKey?: string; pin?: string };
  try {
    payload = (await req.json()) as { host?: string; apiKey?: string; pin?: string };
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
  if (!apiKey) {
    return NextResponse.json(
      { error: "api_key_required", message: "apiKey is required" },
      { status: 400 },
    );
  }
  const pin = String(payload?.pin ?? "");
  if (!pin) {
    return NextResponse.json(
      { error: "pin_required", message: "pin is required" },
      { status: 400 },
    );
  }

  try {
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/dashboard/pin/set`, {
      method: "POST",
      headers: {
        "X-ADOS-Key": apiKey,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ pin }),
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
