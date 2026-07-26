/**
 * Proxy for Betaflight Cloud Build builds API.
 *
 * GET  /api/betaflight/builds?release=4.5.1&target=SPEEDYBEEF405 → get build info
 * GET  /api/betaflight/builds?key=abc123&status=true → poll build status
 * POST /api/betaflight/builds (body: {target, release, options[]}) → request custom build
 */

import { NextRequest, NextResponse } from "next/server";

import { fetchWithTimeout } from "@/lib/net/fetch-with-timeout";

const BETAFLIGHT_BUILDS_API = "https://build.betaflight.com/api/builds";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const key = searchParams.get("key");
  const status = searchParams.get("status");
  const release = searchParams.get("release");
  const target = searchParams.get("target");

  let url: string;

  if (key && status) {
    // Poll build status
    url = `${BETAFLIGHT_BUILDS_API}/${encodeURIComponent(key)}/status`;
  } else if (release && target) {
    // Get build info for target + release
    url = `${BETAFLIGHT_BUILDS_API}/${encodeURIComponent(release)}/${encodeURIComponent(target)}`;
  } else {
    return NextResponse.json(
      { error: "Missing required parameters: (release + target) or (key + status)" },
      { status: 400 },
    );
  }

  try {
    const res = await fetchWithTimeout(url, {
      upstreamSignal: request.signal,
    });
    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      const detail = errBody ? `: ${errBody.slice(0, 200)}` : "";
      return NextResponse.json(
        { error: `Betaflight API returned ${res.status}${detail}` },
        { status: res.status >= 500 ? 502 : res.status },
      );
    }

    const body = await res.text();
    return new NextResponse(body, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Upstream timeout" }, { status: 504 });
    }
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

export async function POST(request: NextRequest) {
  let body: { target: string; release: string; options: string[] };

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.target || !body.release) {
    return NextResponse.json(
      { error: "Missing required fields: target, release" },
      { status: 400 },
    );
  }

  try {
    const res = await fetchWithTimeout(BETAFLIGHT_BUILDS_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: body.target,
        release: body.release,
        options: body.options ?? [],
      }),
      upstreamSignal: request.signal,
    });

    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      const detail = errBody ? `: ${errBody.slice(0, 200)}` : "";
      return NextResponse.json(
        { error: `Betaflight API returned ${res.status}${detail}` },
        { status: res.status >= 500 ? 502 : res.status },
      );
    }

    const responseBody = await res.text();
    return new NextResponse(responseBody, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({ error: "Upstream timeout" }, { status: 504 });
    }
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
