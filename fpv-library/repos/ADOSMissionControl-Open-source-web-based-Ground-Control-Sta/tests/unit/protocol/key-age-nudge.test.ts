import { describe, it, expect, vi, afterEach } from "vitest";

import {
  daysSince,
  KEY_AGE_NUDGE_DAYS,
  KEY_AGE_SNOOZE_DAYS,
} from "@/components/fc/security/KeyAgeNudge";

describe("KeyAgeNudge helpers", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  describe("daysSince", () => {
    it("returns 0 for a just-now timestamp", () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-04-17T12:00:00Z"));
      expect(daysSince("2026-04-17T11:59:00Z")).toBe(0);
    });

    it("returns the exact day count across multiple days", () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-04-17T12:00:00Z"));
      expect(daysSince("2026-04-10T12:00:00Z")).toBe(7);
      expect(daysSince("2026-01-17T12:00:00Z")).toBe(90);
    });

    it("handles a year-old enrollment", () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-04-17T12:00:00Z"));
      expect(daysSince("2025-04-17T12:00:00Z")).toBe(365);
    });

    it("returns null on unparseable input", () => {
      expect(daysSince("not-a-date")).toBeNull();
      expect(daysSince("")).toBeNull();
    });
  });

  describe("constants", () => {
    it("nudge threshold is six months", () => {
      expect(KEY_AGE_NUDGE_DAYS).toBe(180);
    });

    it("snooze is one month", () => {
      expect(KEY_AGE_SNOOZE_DAYS).toBe(30);
    });
  });
});
