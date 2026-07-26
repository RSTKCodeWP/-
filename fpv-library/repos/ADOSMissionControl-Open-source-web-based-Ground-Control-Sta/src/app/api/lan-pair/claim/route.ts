/**
 * @module LanPairClaimRoute
 * @description Server-side proxy for the LAN agent's
 * `/api/pairing/claim` endpoint. Sibling to the probe route.
 *
 * The browser POSTs `{ host, userId }`. Server forwards
 * `{ user_id }` to the agent at the validated host. Body and status
 * are returned verbatim so the pair client can map the agent's
 * standard ClaimResponse without any extra translation.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 8000;

export async function POST(req: NextRequest) {
  let payload: { host?: string; userId?: string };
  try {
    payload = (await req.json()) as {
      host?: string;
      userId?: string;
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

  const userId = String(payload?.userId ?? "").trim();
  if (!userId) {
    return NextResponse.json(
      { error: "user_id_required", message: "userId is required" },
      { status: 400 },
    );
  }

  try {
    // Resolve to IPv4 first so a .local host doesn't stall on AAAA (../_ipv4).
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/pairing/claim`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ user_id: userId }),
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const body = await upstream.text();
    return new NextResponse(body, {
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
