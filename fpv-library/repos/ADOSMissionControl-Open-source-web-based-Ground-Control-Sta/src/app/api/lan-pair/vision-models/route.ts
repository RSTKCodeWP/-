/**
 * @module LanPairVisionModelsRoute
 * @description Server-side proxy for the LAN agent's vision model-registry
 * READ endpoints. Sibling to the write proxies (`vision-detector`,
 * `vision-upload`) so the read half of the model picker is HTTPS-LAN-safe
 * too (Rule 39 local-first): an HTTPS Mission Control can list / download /
 * poll a drone's vision models over the operator's LAN without the browser's
 * mixed-content guard blocking the plain-HTTP fetch, because the cross-protocol
 * hop happens server-side.
 *
 * The browser sends `{ host, apiKey, op, modelId? }`:
 *   - `op: "list"`    -> `GET  /api/vision/models`
 *   - `op: "download"`-> `POST /api/vision/models/{modelId}/download`
 *   - `op: "status"`  -> `GET  /api/vision/models/{modelId}/status`
 * The agent's response body and status are returned verbatim so the client
 * coerces them with the same logic it uses on the direct (HTTP/Electron) path.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 12000;

type VisionReadOp = "list" | "download" | "status";

export async function POST(req: NextRequest) {
  let payload: {
    host?: string;
    apiKey?: string;
    op?: string;
    modelId?: string;
  };
  try {
    payload = (await req.json()) as typeof payload;
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

  const op = String(payload?.op ?? "") as VisionReadOp;
  if (op !== "list" && op !== "download" && op !== "status") {
    return NextResponse.json(
      { error: "bad_op", message: "op must be list, download, or status" },
      { status: 400 },
    );
  }

  const modelId = String(payload?.modelId ?? "").trim();
  if ((op === "download" || op === "status") && !modelId) {
    return NextResponse.json(
      { error: "model_id_required", message: "modelId is required" },
      { status: 400 },
    );
  }

  const apiKey = String(payload?.apiKey ?? "").trim();

  // Compose the upstream path + method from the op. modelId is path-encoded
  // exactly as the direct client does so a model id with special characters
  // round-trips identically over either path.
  const enc = encodeURIComponent(modelId);
  const { path, method } =
    op === "list"
      ? { path: "/api/vision/models", method: "GET" as const }
      : op === "download"
        ? { path: `/api/vision/models/${enc}/download`, method: "POST" as const }
        : { path: `/api/vision/models/${enc}/status`, method: "GET" as const };

  try {
    // Resolve to IPv4 first so a .local host doesn't stall on AAAA (../_ipv4).
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(apiKey ? { "X-ADOS-Key": apiKey } : {}),
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
