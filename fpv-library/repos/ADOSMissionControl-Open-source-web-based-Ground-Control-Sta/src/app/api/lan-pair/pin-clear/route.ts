/**
 * @module LanPairPinClearRoute
 * @description Server-side proxy for the LAN agent's `/api/dashboard/pin/clear`
 * endpoint (reset the dashboard-access PIN).
 *
 * The browser POSTs `{ host, apiKey }`. The server forwards the API key in
 * `X-ADOS-Key`, which the agent's normal auth gate requires for this route.
 * Clearing rotates the salt the session tokens are keyed with, so every browser
 * currently unlocked on that node's dashboard is signed out. Body + status are
 * returned verbatim.
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
  if (!apiKey) {
    return NextResponse.json(
      { error: "api_key_required", message: "apiKey is required" },
      { status: 400 },
    );
  }

  try {
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/dashboard/pin/clear`, {
      method: "POST",
      headers: { "X-ADOS-Key": apiKey, Accept: "application/json" },
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
