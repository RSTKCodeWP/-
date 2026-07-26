import { describe, it, expect } from "vitest";
import { formatLogTime } from "../LogViewer";

describe("formatLogTime", () => {
  it("slices HH:MM:SS out of an ISO-8601 string", () => {
    expect(formatLogTime("2026-05-24T09:30:15+00:00")).toBe("09:30:15");
    expect(formatLogTime("2026-05-24T23:59:59.123Z")).toBe("23:59:59");
  });

  it("formats a numeric epoch in milliseconds", () => {
    const ms = Date.UTC(2026, 4, 24, 9, 30, 15);
    const d = new Date(ms);
    expect(formatLogTime(ms)).toBe(d.toTimeString().slice(0, 8));
  });

  it("formats a numeric epoch in seconds", () => {
    const ms = Date.UTC(2026, 4, 24, 9, 30, 15);
    const d = new Date(ms);
    expect(formatLogTime(ms / 1000)).toBe(d.toTimeString().slice(0, 8));
  });

  it("parses a numeric string as an epoch", () => {
    const ms = Date.UTC(2026, 4, 24, 9, 30, 15);
    const d = new Date(ms);
    expect(formatLogTime(String(ms))).toBe(d.toTimeString().slice(0, 8));
  });

  it("never throws on malformed input", () => {
    expect(formatLogTime(undefined)).toBe("");
    expect(formatLogTime(null)).toBe("");
    expect(formatLogTime(NaN)).toBe("");
    expect(formatLogTime("not a date")).toBe("");
    expect(formatLogTime({})).toBe("");
  });
});
