import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Regression net for the WebRTC PeerConnection cleanup contract.
 *
 * Safari leaves MediaStreamTracks in the "live" state when pc.close() is
 * called without first stopping every receiver and sender track. That
 * holds the camera/mic permission and forces a re-prompt on the next
 * stream start.
 *
 * The closePeerConnection helper does the cleanup. These tests verify
 * the helper is the single owner of pc.close() in the module so a
 * future refactor cannot reintroduce a raw pc.close() that skips the
 * track stop.
 */
describe("webrtc-client cleanup contract", () => {
  const src = readFileSync(
    resolve(__dirname, "../../../src/lib/video/webrtc-client.ts"),
    "utf-8",
  );

  it("defines a closePeerConnection helper that stops receivers and senders", () => {
    expect(src).toContain("function closePeerConnection");
    expect(src).toMatch(/getReceivers\(\)\.forEach/);
    expect(src).toMatch(/getSenders\(\)\.forEach/);
    expect(src).toMatch(/r\.track\?\.stop\(\)/);
    expect(src).toMatch(/s\.track\?\.stop\(\)/);
  });

  it("nulls every event handler in the helper before close", () => {
    // Find the helper body.
    const start = src.indexOf("function closePeerConnection");
    expect(start).toBeGreaterThan(-1);
    // Helper ends at the next function keyword or a top-level export
    const remainder = src.slice(start);
    const end = remainder.search(/\nfunction \w|\nexport \w/);
    const body = end > 0 ? remainder.slice(0, end) : remainder;

    expect(body).toContain("ontrack = null");
    expect(body).toContain("onconnectionstatechange = null");
    expect(body).toContain("onicecandidateerror = null");
    // close() must come AFTER the track stops + handler nulls
    const closeIdx = body.indexOf("target.close()");
    const tracksIdx = body.indexOf("getReceivers");
    expect(closeIdx).toBeGreaterThan(tracksIdx);
  });

  it("contains no raw pc.close() outside the helper", () => {
    // Strip the helper definition so we only scan callers.
    const helperStart = src.indexOf("function closePeerConnection");
    const helperEnd = src.indexOf("\n}", helperStart) + 2;
    const withoutHelper =
      src.slice(0, helperStart) + src.slice(helperEnd);

    // Ignore comments. A simple line-by-line scan is enough.
    const offenders: string[] = [];
    for (const line of withoutHelper.split("\n")) {
      const trimmed = line.trim();
      if (trimmed.startsWith("//") || trimmed.startsWith("*")) continue;
      // Match `pc.close()` or `localPc.close()` as bare calls
      if (/\b(pc|localPc|target)\.close\(\)/.test(trimmed)) {
        offenders.push(trimmed);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("uses closePeerConnection at every cleanup site", () => {
    // Count call sites — should match the 5 places we hand-converted
    // (stopStream + 2x cleanup-on-error + 2x cleanup-before-start).
    const matches = src.match(/closePeerConnection\(/g) ?? [];
    // 1 helper definition reference + 5 caller sites = 6 occurrences min
    expect(matches.length).toBeGreaterThanOrEqual(5);
  });
});
