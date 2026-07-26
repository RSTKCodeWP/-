/**
 * Contract tests for the cloud-relay retention + hygiene surface.
 *
 * Pins the security/perf fixes that are pure source-shape invariants:
 *   - cleanExpiredRequests is cron-only (internalMutation) and walks an index
 *     instead of a full-table .filter().collect().
 *   - terminal command rows + exported log windows have a retention sweep
 *     wired into the cron schedule.
 *   - storage has no generic getUrl resolver that mints a signed URL for any
 *     blob to any authenticated user.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const read = (rel: string) =>
  readFile(path.join(process.cwd(), rel), "utf8");

describe("expired-pairing cleanup is cron-only + indexed", () => {
  it("declares cleanExpiredRequests as an internalMutation", async () => {
    const text = await read("convex/cmdPairing.ts");
    expect(text).toContain("export const cleanExpiredRequests = internalMutation");
    // The public mutation form is gone (no client can trigger the scan).
    expect(text).not.toContain("export const cleanExpiredRequests = mutation");
  });

  it("walks the by_expiresAt index instead of a full-table filter scan", async () => {
    const text = await read("convex/cmdPairing.ts");
    expect(text).toContain('withIndex("by_expiresAt"');
    expect(text).not.toContain('.filter((q) => q.lt(q.field("expiresAt"), now))');
  });

  it("is invoked through the internal API from the cron", async () => {
    const crons = await read("convex/crons.ts");
    expect(crons).toContain("internal.cmdPairing.cleanExpiredRequests");
    expect(crons).not.toContain("api.cmdPairing.cleanExpiredRequests");
  });
});

describe("retention sweeps for append-mostly tables", () => {
  it("prunes terminal command rows on an indexed range", async () => {
    const [commands, crons, schema] = await Promise.all([
      read("convex/cmdDroneCommands.ts"),
      read("convex/crons.ts"),
      read("convex/schema.ts"),
    ]);
    expect(commands).toContain("export const pruneTerminalCommands = internalMutation");
    expect(commands).toContain('withIndex("by_status_completedAt"');
    expect(schema).toContain('.index("by_status_completedAt", ["status", "completedAt"])');
    expect(crons).toContain("internal.cmdDroneCommands.pruneTerminalCommands");
  });

  it("prunes old exported log windows + deletes their blobs", async () => {
    const [windows, crons, schema] = await Promise.all([
      read("convex/cmdLogdWindows.ts"),
      read("convex/crons.ts"),
      read("convex/schema.ts"),
    ]);
    expect(windows).toContain("export const pruneOldWindows = internalMutation");
    expect(windows).toContain('withIndex("by_pushedAt"');
    // The sweep must drop the storage blob so it never orphans storage.
    expect(windows).toContain("ctx.storage.delete(row.storageId)");
    expect(schema).toContain('.index("by_pushedAt", ["pushedAt"])');
    expect(crons).toContain("internal.cmdLogdWindows.pruneOldWindows");
  });

  it("bounds the windows list query instead of an unbounded collect", async () => {
    const text = await read("convex/cmdLogdWindows.ts");
    // getLogdWindows must .take a bounded set, not .collect the whole table.
    const listSlice = text.slice(text.indexOf("export const getLogdWindows"));
    const handlerEnd = listSlice.indexOf("export const getWindowInternal");
    const listBody = listSlice.slice(0, handlerEnd);
    expect(listBody).toContain(".take(MAX_WINDOW_LIST)");
    expect(listBody).not.toContain(".collect()");
  });
});

describe("storage has no over-permissive generic resolver", () => {
  it("does not export a public getUrl that resolves any storageId", async () => {
    const text = await read("convex/storage.ts");
    expect(text).not.toContain("export const getUrl");
    // generateUploadUrl stays (admin-gated).
    expect(text).toContain("export const generateUploadUrl = mutation");
  });
});
