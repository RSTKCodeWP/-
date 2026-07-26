/**
 * @module community-api-logd
 * @description Typed Convex API references for the explicitly-exported
 * durable-log windows surfaced in the ADOS Black Box view. The list query
 * and the signed-download action are resolved through
 * `makeFunctionReference` rather than the generated `api` surface so this
 * barrel keeps type-checking even before the backend module has been picked
 * up by `convex/_generated`. Reads are owner-gated server-side and degrade
 * to an empty list when the account has no exported windows.
 * @license GPL-3.0-only
 */

import { makeFunctionReference } from "convex/server";

/** One exported window record, owner-gated and free of storage internals.
 * Mirrors the read shape returned by the list query (no `storageId` /
 * `userId`). */
export interface LogdWindow {
  _id: string;
  _creationTime: number;
  deviceId: string;
  /** Owning session id, or "" when the window was a raw time range. */
  sessionId: string;
  /** "logs" | "metrics" | "events" | "hw" | "mixed". */
  kind: string;
  windowStartUs: number;
  windowEndUs: number;
  /** Server-recomputed sha256 of the stored bytes, hex. */
  contentHash: string;
  /** "jsonl.zst" | "jsonl". */
  format: string;
  rowCount: number;
  sizeBytes: number;
  /** Epoch ms when the window was stored. */
  pushedAt: number;
}

/** Newest-first list of exported windows for one device, owner-gated. */
export const getLogdWindowsRef = makeFunctionReference<
  "query",
  { deviceId: string },
  LogdWindow[]
>("cmdLogdWindows:getLogdWindows");

/** Signed, time-limited download URL for one exported window, owner-gated. */
export const getLogdWindowRef = makeFunctionReference<
  "action",
  { id: string },
  { url: string | null; window: LogdWindow }
>("cmdLogdWindows:getLogdWindow");
