/**
 * @module RegistryArchiveRoute
 * @description Same-origin proxy that streams a published plugin archive
 * (`.adosplug`) back to the browser. The GCS-side install finalizer
 * fetches the archive to extract its built iframe bundle, but the
 * release CDN does not promise cross-origin access from an arbitrary
 * Mission Control origin, so the fetch happens server-side here and the
 * bytes are returned same-origin.
 *
 * The `url` is allowlisted to the first-party release + registry hosts
 * (an SSRF guard): GitHub release downloads, the GitHub object CDN, and
 * the official ADOS registry host. Anything else is refused.
 *
 * @license GPL-3.0-only
 */

import { NextRequest, NextResponse } from "next/server";

import { OFFICIAL_PLUGIN_REGISTRY_URL } from "@/lib/config/endpoints";

export const runtime = "nodejs";

const UPSTREAM_TIMEOUT_MS = 30_000;
const MAX_BYTES = 64 * 1024 * 1024; // 64 MB ceiling for a plugin archive.

/** Hostname suffixes the proxy will fetch from. A published first-party
 * archive lives on a GitHub release (which 302s to the object CDN) or
 * the official registry host. */
function isAllowedHost(hostname: string): boolean {
  const allowed = [
    "github.com",
    "githubusercontent.com",
    "objects.githubusercontent.com",
  ];
  let registryHost = "";
  try {
    registryHost = new URL(OFFICIAL_PLUGIN_REGISTRY_URL).hostname;
  } catch {
    registryHost = "";
  }
  if (registryHost) allowed.push(registryHost);
  const h = hostname.toLowerCase();
  return allowed.some((a) => h === a || h.endsWith(`.${a}`));
}

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("url");
  if (!raw) {
    return NextResponse.json(
      { error: "missing_url", message: "url query parameter is required" },
      { status: 400 },
    );
  }

  let target: URL;
  try {
    target = new URL(raw);
  } catch {
    return NextResponse.json(
      { error: "bad_url", message: "url is not a valid absolute URL" },
      { status: 400 },
    );
  }

  if (target.protocol !== "https:") {
    return NextResponse.json(
      { error: "bad_scheme", message: "only https archives are proxied" },
      { status: 400 },
    );
  }
  if (!isAllowedHost(target.hostname)) {
    return NextResponse.json(
      {
        error: "host_not_allowed",
        message: `archive host ${target.hostname} is not on the allowlist`,
      },
      { status: 403 },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  let upstream: Response;
  try {
    upstream = await fetch(target.toString(), {
      redirect: "follow",
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    return NextResponse.json(
      {
        error: "fetch_failed",
        message: err instanceof Error ? err.message : String(err),
      },
      { status: 502 },
    );
  }
  clearTimeout(timer);

  if (!upstream.ok) {
    return NextResponse.json(
      {
        error: "upstream_error",
        message: `archive host returned HTTP ${upstream.status}`,
      },
      { status: upstream.status === 404 ? 404 : 502 },
    );
  }

  const declaredLen = Number(upstream.headers.get("content-length") ?? "0");
  if (declaredLen && declaredLen > MAX_BYTES) {
    return NextResponse.json(
      { error: "too_large", message: "archive exceeds the size ceiling" },
      { status: 413 },
    );
  }

  const buf = await upstream.arrayBuffer();
  if (buf.byteLength > MAX_BYTES) {
    return NextResponse.json(
      { error: "too_large", message: "archive exceeds the size ceiling" },
      { status: 413 },
    );
  }

  return new NextResponse(buf, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Cache-Control": "no-store",
    },
  });
}
