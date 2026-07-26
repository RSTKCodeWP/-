"use node";

/**
 * @module pluginRegistryDownload
 * @description Node-runtime action that proxies a `.adosplug` download
 * from the GitHub Releases CDN to the browser. GitHub Releases does
 * not serve `Access-Control-Allow-Origin` headers, so direct browser
 * `fetch()` is blocked by CORS. This action runs server-side, pulls
 * the archive, re-verifies its SHA-256 against the registry row, and
 * either inlines the bytes as base64 (small archives) or stashes the
 * blob in Convex storage and returns a short-lived signed URL.
 *
 * Server-side SHA-256 verification means a tampered or corrupt
 * artifact never reaches the install dialog. The dialog can pipe
 * the returned bytes straight into the existing manifest-parse +
 * LAN-direct / cloud-relay install path.
 *
 * @license GPL-3.0-only
 */

import { v } from "convex/values";
import { createHash } from "node:crypto";

import { action } from "./_generated/server";
import { api } from "./_generated/api";

// Inline-base64 ceiling. Convex action return payloads are capped at
// roughly 8 MiB; we leave headroom for base64 expansion (33%) and
// JSON framing by inlining only when the raw byte count is at or
// under 4 MiB. Larger archives go through Convex storage.
const INLINE_BYTE_CAP = 4 * 1024 * 1024;

// Hard ceiling on the proxied archive size. Matches the registry
// archive size cap in `pluginRegistry.ts`.
const MAX_ARCHIVE_BYTES = 100 * 1024 * 1024;

// Fetch timeout. GitHub Releases CDN normally responds quickly; the
// timeout exists so a hung connection cannot stall the dialog.
const FETCH_TIMEOUT_MS = 60_000;

export const downloadArchive = action({
  args: {
    plugin_id: v.string(),
    version: v.string(),
  },
  handler: async (
    ctx,
    args,
  ): Promise<{
    /** Base64-encoded archive bytes when the payload fits inline.
     * Undefined when the action proxied through Convex storage. */
    bytes_b64?: string;
    /** Short-lived Convex storage URL when the payload was too large
     * to inline. Undefined when the response carries `bytes_b64`. */
    url?: string;
    /** MIME type to attach to the resulting File on the browser side. */
    content_type: string;
    /** Authoritative SHA-256 the server computed over the fetched
     * archive bytes. The browser can re-verify if desired. */
    sha256: string;
    /** Suggested filename, matches `<plugin_id>-<version>.adosplug`. */
    file_name: string;
    /** Final byte count of the archive. */
    size_bytes: number;
  }> => {
    // (1) Resolve the registry row. The version row carries the
    // GitHub download URL and the authoritative SHA-256 the agent
    // and the install dialog will verify against.
    const versionRow = await ctx.runQuery(api.pluginRegistry.getVersion, {
      pluginId: args.plugin_id,
      version: args.version,
    });
    if (!versionRow) {
      throw new Error(
        `Plugin ${args.plugin_id} v${args.version} not found in the registry.`,
      );
    }

    // (2) Confirm the catalog row is still published. A deprecated
    // or removed plugin should not be installable from Browse.
    const catalog = await ctx.runQuery(api.pluginRegistry.getPlugin, {
      pluginId: args.plugin_id,
    });
    if (!catalog || !catalog.plugin) {
      throw new Error(
        `Plugin ${args.plugin_id} is not in the catalog.`,
      );
    }
    if (catalog.plugin.status !== "published") {
      throw new Error(
        `Plugin ${args.plugin_id} is ${catalog.plugin.status} and cannot be installed from the registry.`,
      );
    }

    if (versionRow.archive_size_bytes > MAX_ARCHIVE_BYTES) {
      throw new Error(
        `Archive ${versionRow.archive_size_bytes} bytes exceeds registry cap.`,
      );
    }

    // (3) Fetch the archive from the GitHub Releases CDN server-side.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let response: Response;
    try {
      response = await fetch(versionRow.download_url, {
        signal: controller.signal,
        redirect: "follow",
      });
    } catch (err) {
      throw new Error(
        `Failed to fetch ${versionRow.download_url}: ${
          err instanceof Error ? err.message : String(err)
        }`,
      );
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      throw new Error(
        `Archive host responded ${response.status} ${response.statusText} for ${versionRow.download_url}.`,
      );
    }
    const arrayBuffer = await response.arrayBuffer();
    const bytes = Buffer.from(arrayBuffer);
    if (bytes.byteLength > MAX_ARCHIVE_BYTES) {
      throw new Error(
        `Archive ${bytes.byteLength} bytes exceeds registry cap (${MAX_ARCHIVE_BYTES}).`,
      );
    }
    if (bytes.byteLength !== versionRow.archive_size_bytes) {
      throw new Error(
        `Archive size mismatch: registry says ${versionRow.archive_size_bytes}, host served ${bytes.byteLength}.`,
      );
    }

    // (4) Re-hash the bytes and reject if the registry SHA-256 does
    // not match. This catches host-side corruption or tampering
    // before the dialog hands the bytes to the agent.
    const sha = createHash("sha256").update(bytes).digest("hex").toLowerCase();
    if (sha !== versionRow.archive_sha256.toLowerCase()) {
      throw new Error(
        `Archive SHA-256 mismatch: registry has ${versionRow.archive_sha256}, fetched bytes hash to ${sha}.`,
      );
    }

    const contentType =
      response.headers.get("content-type") ?? "application/zip";
    const fileName = `${args.plugin_id}-${args.version}.adosplug`;

    // (5a) Small archives travel back inline. The browser side
    // decodes the base64 into a Blob and feeds it to the existing
    // manifest-parse pipeline. Faster than a second round-trip
    // through storage.
    if (bytes.byteLength <= INLINE_BYTE_CAP) {
      return {
        bytes_b64: bytes.toString("base64"),
        content_type: contentType,
        sha256: sha,
        file_name: fileName,
        size_bytes: bytes.byteLength,
      };
    }

    // (5b) Large archives go into Convex storage so we stay under the
    // action payload ceiling. Convex storage URLs carry CORS headers,
    // so the browser side can fetch the signed URL directly.
    const storageId = await ctx.storage.store(
      new Blob([new Uint8Array(bytes)], { type: contentType }),
    );
    const storageUrl = await ctx.storage.getUrl(storageId);
    if (!storageUrl) {
      throw new Error("Storage object was rejected after upload.");
    }
    return {
      url: storageUrl,
      content_type: contentType,
      sha256: sha,
      file_name: fileName,
      size_bytes: bytes.byteLength,
    };
  },
});
