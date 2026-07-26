/**
 * Betaflight Cloud Build API client.
 *
 * All requests route through server-side proxy endpoints to avoid CORS.
 * Provides target lookup, release info, custom build requests, and
 * firmware download with hex parsing.
 *
 * @module protocol/firmware/betaflight-manifest
 */

import type {
  BetaflightTarget,
  BetaflightRelease,
  BetaflightBuildInfo,
  BetaflightBuildRequest,
  BetaflightBuildStatus,
  BetaflightBuildOptions,
  ParsedFirmware,
} from "./types";
import { parseHexFile } from "./hex-parser";

export class BetaflightManifest {
  private targetCache: { data: BetaflightTarget[]; timestamp: number } | null = null;
  private readonly CACHE_TTL = 60 * 60 * 1000; // 1 hour

  /** Fetch all available Betaflight targets. Cached for 1 hour. */
  async getTargets(): Promise<BetaflightTarget[]> {
    if (this.targetCache && Date.now() - this.targetCache.timestamp < this.CACHE_TTL) {
      return this.targetCache.data;
    }

    const res = await fetch("/api/betaflight/targets");
    if (!res.ok) {
      throw new Error(`Failed to fetch Betaflight targets: ${res.status}`);
    }

    const data: BetaflightTarget[] = await res.json();
    this.targetCache = { data, timestamp: Date.now() };
    return data;
  }

  /** Fetch available releases for a specific target board. */
  async getReleasesForTarget(target: string): Promise<BetaflightRelease[]> {
    const res = await fetch(`/api/betaflight/targets?target=${encodeURIComponent(target)}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch releases for ${target}: ${res.status}`);
    }

    const data = await res.json();
    // BF API returns different shapes — normalize to BetaflightRelease[]
    if (Array.isArray(data)) {
      return data.map((item: Record<string, unknown>) => ({
        release: String(item.release ?? item.tag ?? item),
        label: typeof item.label === "string" ? item.label : undefined,
      }));
    }
    if (data && Array.isArray(data.releases)) {
      return data.releases as BetaflightRelease[];
    }
    if (data && typeof data.release === "string") {
      return [{ release: data.release, label: typeof data.label === "string" ? data.label : undefined }];
    }
    return [];
  }

  /** Get build info (download URL) for a target + release combination. */
  async getBuildInfo(target: string, release: string): Promise<BetaflightBuildInfo> {
    const params = new URLSearchParams({ target, release });
    const res = await fetch(`/api/betaflight/builds?${params}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch build info for ${target}@${release}: ${res.status}`);
    }
    return res.json();
  }

  /** Download a firmware hex file and parse it into flashable blocks. */
  async downloadFirmware(url: string): Promise<ParsedFirmware> {
    const res = await fetch(`/api/firmware?url=${encodeURIComponent(url)}`);
    if (!res.ok) {
      throw new Error(`Failed to download firmware: ${res.status}`);
    }
    const hexContent = await res.text();
    return parseHexFile(hexContent);
  }

  /** Fetch available build options (radio protocols, motor protocols, etc.) for a release. */
  async getBuildOptions(release: string): Promise<BetaflightBuildOptions> {
    const res = await fetch(`/api/betaflight/options?release=${encodeURIComponent(release)}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch build options for ${release}: ${res.status}`);
    }
    return res.json();
  }

  /** Request a custom cloud build with selected options. */
  async requestBuild(request: BetaflightBuildRequest): Promise<BetaflightBuildStatus> {
    const res = await fetch("/api/betaflight/builds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      throw new Error(`Failed to request build: ${res.status}`);
    }
    return res.json();
  }

  /** Poll the status of a cloud build job by key. */
  async pollBuildStatus(key: string): Promise<BetaflightBuildStatus> {
    const params = new URLSearchParams({ key, status: "true" });
    const res = await fetch(`/api/betaflight/builds?${params}`);
    if (!res.ok) {
      throw new Error(`Failed to poll build status for ${key}: ${res.status}`);
    }
    return res.json();
  }

  /** Clear the target cache. */
  clearCache(): void {
    this.targetCache = null;
  }
}
