/**
 * ArduPilot firmware manifest client.
 *
 * Fetches pre-filtered manifest data from our server-side proxy
 * (/api/manifest) which handles CORS, gzip decompression, and
 * APJ-only filtering. Caches in memory with 1-hour TTL.
 *
 * @module protocol/firmware/manifest
 */

import type { FirmwareManifest, ManifestBoard, ManifestFirmware, ParsedFirmware } from "./types";
import { parseApjFile } from "./apj-parser";
import { parseHexFile } from "./hex-parser";

// ── Constants ──────────────────────────────────────────────

const PROXY_URL = "/api/manifest";
const CACHE_TTL = 60 * 60 * 1000; // 1 hour

// ── ArduPilotManifest ──────────────────────────────────────

export class ArduPilotManifest {
  private manifest: FirmwareManifest | null = null;
  private fetchedAt = 0;

  /** Get the manifest, using in-memory cache if fresh. */
  async getManifest(): Promise<FirmwareManifest> {
    if (this.manifest && Date.now() - this.fetchedAt < CACHE_TTL) {
      return this.manifest;
    }

    const manifest = await this.fetchManifest();
    this.manifest = manifest;
    this.fetchedAt = Date.now();
    return manifest;
  }

  /** Extract unique board names from manifest. */
  async getBoards(): Promise<ManifestBoard[]> {
    const manifest = await this.getManifest();
    const boardMap = new Map<string, Set<string>>();

    for (const fw of manifest.firmwares) {
      if (!fw.board || !fw.vehicleType) continue;

      if (!boardMap.has(fw.board)) {
        boardMap.set(fw.board, new Set());
      }
      boardMap.get(fw.board)!.add(fw.vehicleType);
    }

    return Array.from(boardMap.entries())
      .map(([name, vehicleTypes]) => ({
        name,
        vehicleTypes: Array.from(vehicleTypes).sort(),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  /** Get firmware entries for a specific board, optionally filtered. */
  async getFirmwareForBoard(
    boardName: string,
    vehicleType?: string,
    releaseType?: string,
  ): Promise<ManifestFirmware[]> {
    const manifest = await this.getManifest();
    return manifest.firmwares.filter((fw) => {
      if (fw.board !== boardName) return false;
      if (vehicleType && fw.vehicleType !== vehicleType) return false;
      if (releaseType && fw.releaseType !== releaseType) return false;
      return true;
    });
  }

  /** Get unique release types for a board+vehicle combination, sorted. */
  async getVersions(boardName: string, vehicleType: string): Promise<string[]> {
    const firmwares = await this.getFirmwareForBoard(boardName, vehicleType);

    // Collect unique release types
    const releaseTypes = new Set<string>();
    for (const fw of firmwares) {
      if (fw.releaseType) releaseTypes.add(fw.releaseType);
    }

    // Normalize and sort: stable first, then beta, then dev/latest
    const order = (rt: string): number => {
      const lower = rt.toLowerCase();
      if (lower.startsWith("stable") || lower === "official") return 0;
      if (lower === "beta") return 1;
      if (lower === "latest") return 2;
      if (lower === "dev") return 3;
      return 99;
    };

    return Array.from(releaseTypes).sort((a, b) => order(a) - order(b));
  }

  /** Resolve a firmware download URL for a specific board+type+version. */
  async getFirmwareUrl(boardName: string, vehicleType: string, releaseType: string): Promise<string | null> {
    const firmwares = await this.getFirmwareForBoard(boardName, vehicleType, releaseType);
    const apj = firmwares.find((f) => f.format === "apj");
    return apj?.url ?? null;
  }

  /** Download and parse a firmware file from URL. */
  async downloadFirmware(url: string, options?: { forDfu?: boolean }): Promise<ParsedFirmware> {
    // For DFU flashing, prefer _with_bl.hex (has bootloader + correct addresses)
    if (options?.forDfu && url.endsWith(".apj")) {
      const hexUrl = url.replace(/\.apj$/, "_with_bl.hex");
      try {
        const hexResponse = await fetch(`/api/firmware?url=${encodeURIComponent(hexUrl)}`);
        if (hexResponse.ok) {
          const hexText = await hexResponse.text();
          return parseHexFile(hexText);
        }
      } catch {
        // HEX unavailable — fall back to APJ below
      }
      console.warn("[firmware] _with_bl.hex unavailable — falling back to APJ (address 0x08000000)");
    }

    const response = await fetch(`/api/firmware?url=${encodeURIComponent(url)}`);
    if (!response.ok) {
      throw new Error(`Failed to download firmware: ${response.status} ${response.statusText}`);
    }

    const text = await response.text();

    if (url.endsWith(".apj")) {
      return parseApjFile(text);
    }

    try {
      return parseApjFile(text);
    } catch {
      throw new Error("Unsupported firmware format. Expected .apj file.");
    }
  }

  /** Clear cached manifest. */
  clearCache(): void {
    this.manifest = null;
    this.fetchedAt = 0;
  }

  // ── Private ────────────────────────────────────────────

  private async fetchManifest(): Promise<FirmwareManifest> {
    const response = await fetch(PROXY_URL);

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `Manifest proxy returned ${response.status}`);
    }

    const json = await response.json();

    if (json.error) {
      throw new Error(json.error);
    }

    const firmwares: ManifestFirmware[] = (json.firmwares || []).map(
      (entry: Record<string, string>) => ({
        board: entry.board || "",
        vehicleType: entry.vehicleType || "",
        version: entry.version || "",
        releaseType: entry.releaseType || "",
        url: entry.url || "",
        format: entry.format || "apj",
        gitHash: entry.gitHash,
        buildDate: entry.buildDate,
      }),
    );

    return {
      firmwares,
      formatVersion: json.formatVersion,
    };
  }
}
