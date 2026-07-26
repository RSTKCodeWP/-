import { describe, it, expect } from "vitest";

import {
  classifyVariant,
  MISMATCH_WINDOW_MS,
  VARIANTS,
  type BadgeClassifyInput,
  type SigningBadgeVariant,
} from "@/components/command/SigningStatusBadge";

const NOW = 1_700_000_000_000;

function input(partial: Partial<BadgeClassifyInput>): BadgeClassifyInput {
  return {
    capability: null,
    hasBrowserKey: false,
    ...partial,
  };
}

describe("classifyVariant", () => {
  it("returns loading when state is missing", () => {
    expect(classifyVariant(undefined, NOW)).toBe("loading");
  });

  it("returns loading when capability is null", () => {
    expect(classifyVariant(input({ capability: null }), NOW)).toBe("loading");
  });

  it("returns na when firmware does not support signing", () => {
    expect(
      classifyVariant(input({ capability: { supported: false } }), NOW),
    ).toBe("na");
  });

  it("returns key_missing when the enrollment state says so", () => {
    const r = classifyVariant(
      input({
        capability: { supported: true },
        hasBrowserKey: false,
        enrollmentState: "key_missing",
      }),
      NOW,
    );
    expect(r).toBe("key_missing");
  });

  it("returns mismatch when recent signed frames were rejected", () => {
    const r = classifyVariant(
      input({
        capability: { supported: true },
        hasBrowserKey: true,
        enrollmentState: "enrolled",
        rxInvalidCount: 5,
        lastSignedFrameAt: NOW - 1000,
      }),
      NOW,
    );
    expect(r).toBe("mismatch");
  });

  it("does not return mismatch when the last signed frame is outside the window", () => {
    const r = classifyVariant(
      input({
        capability: { supported: true },
        hasBrowserKey: true,
        enrollmentState: "enrolled",
        rxInvalidCount: 5,
        lastSignedFrameAt: NOW - (MISMATCH_WINDOW_MS + 1000),
      }),
      NOW,
    );
    expect(r).toBe("signed");
  });

  it("returns signed when enrolled and require is off", () => {
    const r = classifyVariant(
      input({
        capability: { supported: true },
        hasBrowserKey: true,
        enrollmentState: "enrolled",
        requireOnFc: false,
      }),
      NOW,
    );
    expect(r).toBe("signed");
  });

  it("returns signed_required when enrolled and require is on", () => {
    const r = classifyVariant(
      input({
        capability: { supported: true },
        hasBrowserKey: true,
        enrollmentState: "enrolled",
        requireOnFc: true,
      }),
      NOW,
    );
    expect(r).toBe("signed_required");
  });

  it("returns unsigned when supported but no browser key", () => {
    const r = classifyVariant(
      input({ capability: { supported: true }, hasBrowserKey: false }),
      NOW,
    );
    expect(r).toBe("unsigned");
  });
});

describe("VARIANTS", () => {
  it("has every variant present", () => {
    const expected: SigningBadgeVariant[] = [
      "signed",
      "signed_required",
      "unsigned",
      "key_missing",
      "mismatch",
      "na",
      "loading",
    ];
    for (const k of expected) {
      expect(VARIANTS[k]).toBeDefined();
    }
  });

  it("every variant ships an aria-label distinct from its sibling variants", () => {
    const labels = Object.values(VARIANTS).map((v) => v.ariaLabel);
    const unique = new Set(labels);
    expect(unique.size).toBe(labels.length);
  });

  it("every variant has non-empty tooltip, label, and className", () => {
    for (const [name, v] of Object.entries(VARIANTS)) {
      expect(v.label, `${name}.label`).toBeTruthy();
      expect(v.tooltip, `${name}.tooltip`).toBeTruthy();
      expect(v.className, `${name}.className`).toBeTruthy();
      expect(v.ariaLabel, `${name}.ariaLabel`).toBeTruthy();
    }
  });
});
