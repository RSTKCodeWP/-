/**
 * Proxy for Betaflight Cloud Build targets API.
 *
 * GET /api/betaflight/targets → list all targets
 * GET /api/betaflight/targets?target=SPEEDYBEEF405 → get specific target info
 *
 * Server-side cache with 1 hour TTL.
 */

import { NextRequest, NextResponse } from "next/server";

import { fetchWithTimeout } from "@/lib/net/fetch-with-timeout";

const BETAFLIGHT_API = "https://build.betaflight.com/api/targets";
const CACHE_TTL = 60 * 60 * 1000; // 1 hour

const cache = new Map<string, { data: string; timestamp: number }>();

export async function GET(request: NextRequest) {
  const target = request.nextUrl.searchParams.get("target");
  const cacheKey = target ?? "__all__";

  // Check cache
  const cached = cache.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return new NextResponse(cached.data, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const url = target ? `${BETAFLIGHT_API}/${encodeURIComponent(target)}` : BETAFLIGHT_API;

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
    cache.set(cacheKey, { data: body, timestamp: Date.now() });

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
