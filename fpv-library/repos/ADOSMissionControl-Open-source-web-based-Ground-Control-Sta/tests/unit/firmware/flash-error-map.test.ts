/**
 * Unit tests for the flash error categoriser and remedy map.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { categorize, mapError } from "@/components/fc/firmware/flash-error-map";

describe("flash-error-map categorize", () => {
  it("maps a re-enumeration / disconnect to device_disconnected", () => {
    expect(categorize(new DOMException("lost", "NetworkError"))).toBe("device_disconnected");
    expect(categorize(new Error("Serial read ended — device disconnected"))).toBe("device_disconnected");
  });

  it("maps a sync failure to sync_timeout", () => {
    expect(categorize(new Error("Failed to synchronize with PX4 bootloader"))).toBe("sync_timeout");
    expect(categorize(new Error("Serial read timeout: expected 2 bytes"))).toBe("sync_timeout");
  });

  it("maps board id and crc failures", () => {
    expect(categorize(new Error("Board ID mismatch: firmware expects 50"))).toBe("board_id_mismatch");
    expect(categorize(new Error("CRC32 mismatch: local 0xabc"))).toBe("crc_mismatch");
  });

  it("maps browser/permission failures", () => {
    expect(categorize(new DOMException("blocked", "SecurityError"))).toBe("webusb_blocked");
    expect(categorize(new DOMException("none", "NotFoundError"))).toBe("no_device");
  });

  it("treats aborts and unknowns distinctly", () => {
    expect(categorize(new Error("Flash aborted by user"))).toBe("aborted");
    expect(categorize(new Error("something weird"))).toBe("unknown");
  });
});

describe("flash-error-map mapError", () => {
  it("routes a disconnect to the select-bootloader action", () => {
    const r = mapError("device_disconnected");
    expect(r.primaryAction).toBe("select-bootloader");
    expect(r.showManualBootloader).toBe(true);
    expect(r.titleKey).toBe("deviceDisconnected.title");
  });

  it("routes a sync timeout to retry with recovery steps", () => {
    const r = mapError("sync_timeout");
    expect(r.primaryAction).toBe("retry");
    expect(r.stepKeys.length).toBeGreaterThan(0);
  });

  it("does not offer retry on a board id mismatch", () => {
    const r = mapError("board_id_mismatch");
    expect(r.primaryAction).toBeUndefined();
  });
});
