/**
 * Proxy for Betaflight Cloud Build options API.
 *
 * GET /api/betaflight/options?release=4.5.1 → get available build options for a release
 */

import { NextRequest, NextResponse } from "next/server";

import { fetchWithTimeout } from "@/lib/net/fetch-with-timeout";

const BETAFLIGHT_OPTIONS_API = "https://build.betaflight.com/api/options";

export async function GET(request: NextRequest) {
  const release = request.nextUrl.searchParams.get("release");

  if (!release) {
    return NextResponse.json(
      { error: "Missing required parameter: release" },
      { status: 400 },
    );
  }

  const url = `${BETAFLIGHT_OPTIONS_API}/${encodeURIComponent(release)}`;

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
