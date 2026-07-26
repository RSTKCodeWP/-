/**
 * PX4 firmware manifest — fetches PX4 releases from GitHub via server proxy.
 *
 * Queries /api/px4/releases which proxies to the GitHub Releases API
 * for PX4/PX4-Autopilot. Caches results for 1 hour. Downloads .px4
 * firmware files via /api/firmware proxy and parses them.
 *
 * @module protocol/firmware/px4-manifest
 */

import type { PX4Release, PX4Board, ParsedFirmware } from "./types";
import { parsePx4File } from "./px4-parser";

interface ReleaseCache {
  data: PX4Release[];
  timestamp: number;
}

export class PX4Manifest {
  private releaseCache: ReleaseCache | null = null;
  private readonly CACHE_TTL = 60 * 60 * 1000; // 1 hour

  /**
   * Fetch all PX4 releases that contain .px4 firmware assets.
   * Results are cached for 1 hour.
   */
  async getReleases(): Promise<PX4Release[]> {
    if (
      this.releaseCache &&
      Date.now() - this.releaseCache.timestamp < this.CACHE_TTL
    ) {
      return this.releaseCache.data;
    }

    const res = await fetch("/api/px4/releases");
    if (!res.ok) {
      throw new Error(`Failed to fetch PX4 releases: ${res.status} ${res.statusText}`);
    }

    const data: PX4Release[] = await res.json();
    this.releaseCache = { data, timestamp: Date.now() };
    return data;
  }

  /**
   * Get all boards available for a specific release tag.
   */
  async getBoardsForRelease(tag: string): Promise<PX4Board[]> {
    const releases = await this.getReleases();
    const release = releases.find((r) => r.tag === tag);
    return release?.boards ?? [];
  }

  /**
   * Get the download URL for a specific board in a specific release.
   * Returns null if the board or release is not found.
   */
  async getFirmwareUrl(tag: string, boardName: string): Promise<string | null> {
    const boards = await this.getBoardsForRelease(tag);
    const board = boards.find((b) => b.name === boardName);
    return board?.assetUrl ?? null;
  }

  /**
   * Download a .px4 firmware file and parse it.
   * Uses /api/firmware proxy to bypass CORS.
   */
  async downloadFirmware(url: string): Promise<ParsedFirmware> {
    const proxyUrl = `/api/firmware?url=${encodeURIComponent(url)}`;
    const res = await fetch(proxyUrl);
    if (!res.ok) {
      throw new Error(`Failed to download PX4 firmware: ${res.status} ${res.statusText}`);
    }

    const text = await res.text();
    return parsePx4File(text);
  }

  /** Clear the release cache. */
  clearCache(): void {
    this.releaseCache = null;
  }
}
