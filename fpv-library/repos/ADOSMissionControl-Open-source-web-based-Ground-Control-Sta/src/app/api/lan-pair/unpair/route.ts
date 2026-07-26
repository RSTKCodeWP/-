/**
 * @module LanPairUnpairRoute
 * @description Server-side proxy for the LAN agent's
 * `/api/pairing/unpair` endpoint.
 *
 * The browser POSTs `{ host, apiKey }`. Server forwards the API key
 * in the `X-ADOS-Key` header the agent's auth middleware reads. Body
 * and status are returned verbatim. The API key stays under browser
 * control — it
 * never lands in cookies or Mission Control's database; it just
 * relays through the server in one request.
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
    payload = (await req.json()) as {
      host?: string;
      apiKey?: string;
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

  const apiKey = String(payload?.apiKey ?? "").trim();
  if (!apiKey) {
    return NextResponse.json(
      { error: "api_key_required", message: "apiKey is required" },
      { status: 400 },
    );
  }

  try {
    // Resolve to IPv4 first so a .local host doesn't stall on AAAA (../_ipv4).
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/pairing/unpair`, {
      method: "POST",
      headers: {
        "X-ADOS-Key": apiKey,
        Accept: "application/json",
      },
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
