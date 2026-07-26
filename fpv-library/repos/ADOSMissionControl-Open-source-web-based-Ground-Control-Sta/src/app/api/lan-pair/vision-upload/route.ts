/**
 * @module LanPairVisionUploadRoute
 * @description Server-side proxy for the LAN agent's
 * `POST /api/vision/models/upload` (multipart) endpoint. Sibling to the
 * pairing proxy routes (Rule 39 local-first): lets an HTTPS Mission
 * Control sideload a custom vision model to a drone over the operator's
 * LAN without the browser's mixed-content guard blocking the
 * cross-protocol upload.
 *
 * The browser POSTs a `multipart/form-data` body carrying `host`,
 * `apiKey`, `file`, and `metadata` (a JSON string). The server reads the
 * routing fields, rebuilds a clean multipart with just `file` + `metadata`,
 * and forwards it with the `X-ADOS-Key` header. The agent's response body
 * and status are returned verbatim.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";
import { normaliseAndCheckHost } from "@/lib/agent/host-validation";
import { ipv4FetchBase } from "../_ipv4";

export const runtime = "nodejs";

// Uploads can be tens of MB over a LAN; give the round-trip room.
const UPSTREAM_TIMEOUT_MS = 120000;

export async function POST(req: NextRequest) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "bad_form", message: "Request body must be multipart/form-data" },
      { status: 400 },
    );
  }

  const host = String(form.get("host") ?? "").trim();
  const target = normaliseAndCheckHost(host);
  if ("error" in target) {
    return NextResponse.json(
      { error: target.error, message: target.message },
      { status: 400 },
    );
  }

  const apiKey = String(form.get("apiKey") ?? "").trim();

  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "file_required", message: "file is required" },
      { status: 400 },
    );
  }
  const metadata = form.get("metadata");
  if (typeof metadata !== "string") {
    return NextResponse.json(
      { error: "metadata_required", message: "metadata json is required" },
      { status: 400 },
    );
  }

  // Rebuild a clean upstream form so the routing-only fields (host/apiKey)
  // never reach the agent.
  const upstreamForm = new FormData();
  upstreamForm.append("file", file, file.name);
  upstreamForm.append("metadata", metadata);

  try {
    const base = await ipv4FetchBase(target);
    const upstream = await fetch(`${base}/api/vision/models/upload`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        ...(apiKey ? { "X-ADOS-Key": apiKey } : {}),
      },
      body: upstreamForm,
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
