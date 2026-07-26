import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Recovery contract for the MSE player. The relay can keep a socket open
 * while the decoder silently wedges (no onclose, no error). The player
 * must detect that via a currentTime-advance watchdog and via
 * sourceBuffer error/abort, then reconnect from scratch rather than
 * waiting for an onclose that may never arrive.
 */
describe("mse-player recovery contract", () => {
  const src = readFileSync(
    resolve(__dirname, "../../../src/lib/video/mse-player.ts"),
    "utf-8",
  );

  it("runs a playback-stall watchdog over currentTime", () => {
    expect(src).toContain("startStallWatchdog");
    expect(src).toContain("PLAYBACK_STALL_TIMEOUT_MS");
    expect(src).toMatch(/currentTime\s*>\s*this\.lastPlaybackTime/);
  });

  it("treats sourceBuffer error and abort as unrecoverable", () => {
    expect(src).toMatch(/addEventListener\(\s*"error"/);
    expect(src).toMatch(/addEventListener\(\s*"abort"/);
  });

  it("reconnects without waiting on onclose", () => {
    expect(src).toContain("scheduleReconnect");
    expect(src).toContain("private reconnect()");
    // The stall watchdog and sourceBuffer handlers both route through the
    // debounced scheduler.
    const matches = src.match(/this\.scheduleReconnect\(\)/g) ?? [];
    expect(matches.length).toBeGreaterThanOrEqual(3);
  });

  it("clears the stall timer on stop", () => {
    expect(src).toMatch(/clearInterval\(this\.stallTimer\)/);
  });

  it("does not reconnect on an intentional teardown", () => {
    // stop() must detach onclose before close() and latch a teardown flag
    // that scheduleReconnect() honours, so a deliberate stop never bounces
    // into a reconnect.
    expect(src).toContain("this.tearingDown = true");
    expect(src).toMatch(/this\.ws\.onclose\s*=\s*null/);
    expect(src).toMatch(/if\s*\(this\.tearingDown[\s\S]*?\)\s*return/);
  });
});
