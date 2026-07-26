/**
 * @module LanPairVisionDetectorRoute
 * @description Server-side proxy for the LAN agent's
 * `PUT /api/vision/detector` endpoint. Sibling to the pairing proxy
 * routes (Rule 39 local-first): lets an HTTPS Mission Control set a
 * drone's active detector over the operator's LAN without tripping the
 * browser's mixed-content guard, since the cross-protocol hop happens
 * server-side.
 *
 * The browser POSTs `{ host, apiKey, modelId }`. The server forwards
 * `PUT { model_id }` with the `X-ADOS-Key` header. Body and status are
 * returned verbatim so the client maps the agent's response without
 * extra translation.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 12000;

export async function POST(req: NextRequest) {
  let payload: { host?: string; apiKey?: string; modelId?: string };
  try {
    payload = (await req.json()) as {
      host?: string;
      apiKey?: string;
      modelId?: string;
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

  const modelId = String(payload?.modelId ?? "").trim();
  if (!modelId) {
    return NextResponse.json(
      { error: "model_id_required", message: "modelId is required" },
      { status: 400 },
    );
  }

  const apiKey = String(payload?.apiKey ?? "").trim();

  try {
    // Resolve to IPv4 first so a .local host doesn't stall on AAAA (../_ipv4).
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/vision/detector`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(apiKey ? { "X-ADOS-Key": apiKey } : {}),
      },
      body: JSON.stringify({ model_id: modelId }),
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
